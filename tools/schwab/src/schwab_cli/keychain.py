import platform
import subprocess

from schwab_cli.config import (
    KEYCHAIN_BWS_ORG_SERVICE,
    KEYCHAIN_BWS_TOKEN_SERVICE,
    KEYCHAIN_SCHWAB_ACCOUNT,
    KEYCHAIN_SCHWAB_SERVICE,
)


class KeychainError(RuntimeError):
    pass


def _require_macos() -> None:
    if platform.system() != "Darwin":
        msg = "Schwab CLI Keychain access is supported on macOS only."
        raise KeychainError(msg)


def read_generic_password(*, service: str, account: str | None = None) -> str:
    _require_macos()
    cmd = ["security", "find-generic-password", "-s", service, "-w"]
    if account is not None:
        cmd = ["security", "find-generic-password", "-a", account, "-s", service, "-w"]
    try:
        completed = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        msg = f"Could not read Keychain item for service {service!r}."
        if detail:
            msg = f"{msg} ({detail})"
        raise KeychainError(msg) from exc
    value = completed.stdout.rstrip("\n")
    if not value:
        msg = f"Keychain item for service {service!r} has an empty secret."
        raise KeychainError(msg)
    return value


def write_generic_password(
    *,
    service: str,
    account: str,
    secret: str,
) -> None:
    _require_macos()
    add_cmd = [
        "security",
        "add-generic-password",
        "-a",
        account,
        "-s",
        service,
        "-w",
        secret,
        "-U",
    ]
    try:
        subprocess.run(
            add_cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        msg = f"Could not write Keychain item {service!r} / {account!r}."
        if detail:
            msg = f"{msg} ({detail})"
        raise KeychainError(msg) from exc


def read_bws_access_token() -> str:
    return read_generic_password(service=KEYCHAIN_BWS_TOKEN_SERVICE)


def read_bws_org_id() -> str:
    return read_generic_password(service=KEYCHAIN_BWS_ORG_SERVICE)


def read_schwab_token_blob() -> str:
    return read_generic_password(
        service=KEYCHAIN_SCHWAB_SERVICE,
        account=KEYCHAIN_SCHWAB_ACCOUNT,
    )


def write_schwab_token_blob(blob: str) -> None:
    write_generic_password(
        service=KEYCHAIN_SCHWAB_SERVICE,
        account=KEYCHAIN_SCHWAB_ACCOUNT,
        secret=blob,
    )
    readback = read_schwab_token_blob()
    if readback != blob:
        msg = (
            "Schwab OAuth tokens were not stored correctly in Keychain. "
            "Try `pnpm schwab login` again."
        )
        raise KeychainError(msg)
