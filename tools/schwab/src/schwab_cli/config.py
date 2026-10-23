from pathlib import Path

API_BASE = "https://api.schwabapi.com"
AUTH_URL = f"{API_BASE}/v1/oauth/authorize"
TOKEN_URL = f"{API_BASE}/v1/oauth/token"
CALLBACK_URL = "https://127.0.0.1:8182/api/schwab/callback"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8182
CALLBACK_PATH = "/api/schwab/callback"

KEYCHAIN_BWS_TOKEN_SERVICE = "bws-access-token"
KEYCHAIN_BWS_ORG_SERVICE = "bws-org-id"
KEYCHAIN_SCHWAB_SERVICE = "investor-basecamp"
KEYCHAIN_SCHWAB_ACCOUNT = "schwab"

SECRET_SCHWAB_CLIENT_ID = "SCHWAB_CLIENT_ID"
SECRET_SCHWAB_CLIENT_SECRET = "SCHWAB_CLIENT_SECRET"

TOKEN_EXPIRY_BUFFER_SECONDS = 60


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def local_schwab_dir() -> Path:
    return repo_root() / ".local" / "schwab"


def captures_dir() -> Path:
    return local_schwab_dir() / "captures"


def lock_path() -> Path:
    return local_schwab_dir() / "token.lock"


def bws_state_path() -> Path:
    return local_schwab_dir() / "bws-state"


def tls_cert_path() -> Path:
    return local_schwab_dir() / "certificates" / "cert.pem"


def tls_key_path() -> Path:
    return local_schwab_dir() / "certificates" / "key.pem"
