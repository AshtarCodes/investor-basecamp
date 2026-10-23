import base64
import secrets
import ssl
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import httpx

from schwab_cli.config import (
    AUTH_URL,
    CALLBACK_HOST,
    CALLBACK_PATH,
    CALLBACK_PORT,
    CALLBACK_URL,
    TOKEN_URL,
    tls_cert_path,
    tls_key_path,
)
from schwab_cli.lockfile import token_lock
from schwab_cli.tokens import SchwabTokens, save_tokens


class OAuthError(RuntimeError):
    pass


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode("ascii")


def build_authorize_url(*, client_id: str, state: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": CALLBACK_URL,
            "response_type": "code",
            "state": state,
        }
    )
    return f"{AUTH_URL}?{query}"


def exchange_code_for_tokens(
    *,
    client_id: str,
    client_secret: str,
    code: str,
) -> SchwabTokens:
    headers = {
        "Authorization": _basic_auth_header(client_id, client_secret),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": CALLBACK_URL,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(TOKEN_URL, headers=headers, data=data)
    if response.status_code != 200:
        msg = f"Schwab token exchange failed with HTTP {response.status_code}."
        raise OAuthError(msg)
    return SchwabTokens.from_oauth_response(response.json())


def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> SchwabTokens:
    headers = {
        "Authorization": _basic_auth_header(client_id, client_secret),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(TOKEN_URL, headers=headers, data=data)
    if response.status_code != 200:
        msg = (
            f"Schwab token refresh failed with HTTP {response.status_code}. "
            "Run `pnpm schwab login` if the refresh token expired."
        )
        raise OAuthError(msg)
    return SchwabTokens.from_oauth_response(response.json())


@dataclass
class _CallbackResult:
    code: str | None = None
    error: str | None = None


class _OAuthHandler(BaseHTTPRequestHandler):
    expected_state: str = ""
    result: _CallbackResult | None = None
    shutdown_event: threading.Event | None = None

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_error(404)
            return

        params = urllib.parse.parse_qs(parsed.query)
        state_values = params.get("state", [])
        if not state_values or state_values[0] != self.expected_state:
            if self.result is not None:
                self.result.error = "OAuth state mismatch."
            self.send_error(400, "Invalid OAuth state")
            self._shutdown()
            return

        code_values = params.get("code", [])
        if not code_values:
            if self.result is not None:
                self.result.error = "Missing authorization code."
            self.send_error(400, "Missing code")
            self._shutdown()
            return

        if self.result is not None:
            self.result.code = code_values[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Schwab login received. You can close this tab.")
        self._shutdown()

    def _shutdown(self) -> None:
        if self.shutdown_event is not None:
            self.shutdown_event.set()


def run_login_flow(*, client_id: str, client_secret: str) -> None:
    cert = tls_cert_path()
    key = tls_key_path()
    if not cert.is_file() or not key.is_file():
        msg = (
            "TLS certificate for the login listener is missing. "
            f"Create {cert} and {key} with mkcert (see tools/schwab/README.md)."
        )
        raise OAuthError(msg)

    state = secrets.token_urlsafe(32)
    result = _CallbackResult()
    shutdown_event = threading.Event()

    handler_cls = _OAuthHandler
    handler_cls.expected_state = state
    handler_cls.result = result
    handler_cls.shutdown_event = shutdown_event

    httpd = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), handler_cls)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    authorize_url = build_authorize_url(client_id=client_id, state=state)
    print(f"Opening browser for Schwab login ({CALLBACK_URL}).")
    webbrowser.open(authorize_url)

    if not shutdown_event.wait(timeout=300):
        httpd.shutdown()
        msg = "Timed out waiting for Schwab OAuth callback."
        raise OAuthError(msg)

    httpd.shutdown()
    server_thread.join(timeout=5)

    if result.error:
        raise OAuthError(result.error)
    if not result.code:
        msg = "Schwab OAuth callback did not include an authorization code."
        raise OAuthError(msg)

    with token_lock():
        tokens = exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            code=result.code,
        )
        save_tokens(tokens)

    print("Schwab login succeeded. Tokens saved to Keychain.")
