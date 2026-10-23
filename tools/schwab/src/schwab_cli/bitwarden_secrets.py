from bitwarden_sdk import BitwardenClient, DeviceType, client_settings_from_dict

from schwab_cli.config import (
    SECRET_SCHWAB_CLIENT_ID,
    SECRET_SCHWAB_CLIENT_SECRET,
    bws_state_path,
    local_schwab_dir,
)
from schwab_cli.keychain import read_bws_access_token, read_bws_org_id


class BitwardenSecretsError(RuntimeError):
    pass


def _client() -> tuple[BitwardenClient, str]:
    local_schwab_dir().mkdir(parents=True, exist_ok=True)
    state_path = bws_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if not state_path.exists():
        state_path.touch()

    client = BitwardenClient(
        client_settings_from_dict(
            {
                "apiUrl": "https://api.bitwarden.com",
                "deviceType": DeviceType.SDK,
                "identityUrl": "https://identity.bitwarden.com",
                "userAgent": "investor-basecamp-schwab-cli",
            }
        )
    )
    access_token = read_bws_access_token()
    org_id = read_bws_org_id()
    client.auth().login_access_token(access_token, str(state_path))
    return client, org_id


def _secret_value(client: BitwardenClient, org_id: str, key: str) -> str:
    listed = client.secrets().list(org_id)
    match = next((item for item in listed.data if item.key == key), None)
    if match is None:
        msg = f"Bitwarden secret {key!r} was not found in the organization."
        raise BitwardenSecretsError(msg)
    fetched = client.secrets().get(str(match.id))
    value = fetched.data.value
    if not value:
        msg = f"Bitwarden secret {key!r} has an empty value."
        raise BitwardenSecretsError(msg)
    return value


def load_schwab_app_credentials() -> tuple[str, str]:
    client, org_id = _client()
    client_id = _secret_value(client, org_id, SECRET_SCHWAB_CLIENT_ID)
    client_secret = _secret_value(client, org_id, SECRET_SCHWAB_CLIENT_SECRET)
    return client_id, client_secret
