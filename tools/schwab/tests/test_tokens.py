import pytest

from schwab_cli.tokens import SchwabTokens


def test_from_json_rejects_missing_fields():
    with pytest.raises(KeyError):
        SchwabTokens.from_json("{}")


def test_round_trip_json():
    tokens = SchwabTokens(
        access_token="access",
        refresh_token="refresh",
        expires_at=1_700_000_000.0,
    )
    restored = SchwabTokens.from_json(tokens.to_json())
    assert restored.access_token == "access"
    assert restored.refresh_token == "refresh"
