import json
import time
from dataclasses import dataclass
from typing import Any

from schwab_cli.config import TOKEN_EXPIRY_BUFFER_SECONDS
from schwab_cli.keychain import (
    KeychainError,
    read_schwab_token_blob,
    write_schwab_token_blob,
)


@dataclass
class SchwabTokens:
    access_token: str
    refresh_token: str
    expires_at: float
    token_type: str = "Bearer"

    @classmethod
    def from_oauth_response(cls, payload: dict[str, Any]) -> "SchwabTokens":
        expires_in = float(payload.get("expires_in", 1800))
        refresh = payload.get("refresh_token")
        access = payload.get("access_token")
        if not access or not refresh:
            msg = "Schwab token response is missing access_token or refresh_token."
            raise ValueError(msg)
        return cls(
            access_token=access,
            refresh_token=refresh,
            expires_at=time.time() + expires_in,
            token_type=str(payload.get("token_type", "Bearer")),
        )

    def needs_refresh(self) -> bool:
        return time.time() >= self.expires_at - TOKEN_EXPIRY_BUFFER_SECONDS

    def to_json(self) -> str:
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.expires_at,
                "token_type": self.token_type,
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> "SchwabTokens":
        data = json.loads(raw)
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=float(data["expires_at"]),
            token_type=str(data.get("token_type", "Bearer")),
        )


def load_tokens() -> SchwabTokens:
    try:
        return SchwabTokens.from_json(read_schwab_token_blob())
    except KeychainError as exc:
        msg = (
            "Schwab OAuth tokens are not in Keychain. Run `pnpm schwab login` first."
        )
        raise KeychainError(msg) from exc
    except (json.JSONDecodeError, KeyError) as exc:
        msg = "Schwab Keychain token data is corrupt. Run `pnpm schwab login` again."
        raise ValueError(msg) from exc


def save_tokens(tokens: SchwabTokens) -> None:
    write_schwab_token_blob(tokens.to_json())
