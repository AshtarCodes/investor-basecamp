import pytest

from schwab_cli.paths import assert_get_path_allowed, normalize_api_path


def test_normalize_strips_host_and_ensures_leading_slash():
    assert normalize_api_path("/trader/v1/accounts") == "/trader/v1/accounts"
    assert normalize_api_path("trader/v1/accounts") == "/trader/v1/accounts"


def test_rejects_orders_paths():
    with pytest.raises(ValueError, match="orders"):
        assert_get_path_allowed("/trader/v1/accounts/123/orders")


def test_allows_accounts_and_marketdata():
    assert_get_path_allowed("/trader/v1/accounts/accountNumbers")
    assert_get_path_allowed("/marketdata/v1/quotes?symbols=AAPL")
