from dataclasses import dataclass

import httpx

from schwab_cli.bitwarden_secrets import load_schwab_app_credentials
from schwab_cli.config import API_BASE
from schwab_cli.lockfile import token_lock
from schwab_cli.oauth import refresh_access_token
from schwab_cli.paths import assert_get_path_allowed
from schwab_cli.tokens import SchwabTokens, load_tokens, save_tokens


@dataclass
class SchwabResponse:
    status_code: int
    text: str
    url: str


def _ensure_fresh_tokens() -> SchwabTokens:
    tokens = load_tokens()
    if not tokens.needs_refresh():
        return tokens

    client_id, client_secret = load_schwab_app_credentials()
    with token_lock():
        tokens = load_tokens()
        if not tokens.needs_refresh():
            return tokens
        refreshed = refresh_access_token(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=tokens.refresh_token,
        )
        save_tokens(refreshed)
        return refreshed


def schwab_get(path: str) -> SchwabResponse:
    normalized = assert_get_path_allowed(path)
    tokens = _ensure_fresh_tokens()
    url = f"{API_BASE}{normalized}"
    headers = {"Authorization": f"{tokens.token_type} {tokens.access_token}"}
    with httpx.Client(timeout=60.0) as client:
        response = client.get(url, headers=headers)
    return SchwabResponse(
        status_code=response.status_code,
        text=response.text,
        url=url,
    )
