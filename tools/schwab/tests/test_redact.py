import json

from schwab_cli.redact import redact_account_numbers


def test_redacts_account_number_field_in_json():
    raw = json.dumps({"accountNumber": "12345678", "hashValue": "abc", "totalVolume": 12345678})
    out = json.loads(redact_account_numbers(raw))
    assert out["accountNumber"] == "REDACTED:8-digits"
    assert out["hashValue"] == "abc"
    assert out["totalVolume"] == 12345678


def test_fallback_redacts_bare_eight_digits_in_non_json():
    raw = "account 12345678 end"
    assert redact_account_numbers(raw) == "account REDACTED:8-digits end"


def test_leaves_shorter_digit_runs():
    raw = '{"quantity":100}'
    assert redact_account_numbers(raw) == '{"quantity":100}'
