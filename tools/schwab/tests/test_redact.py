from schwab_cli.redact import redact_account_numbers


def test_redacts_eight_digit_account_number_in_json():
    raw = '{"accountNumber":"12345678","hashValue":"abc"}'
    assert redact_account_numbers(raw) == '{"accountNumber":"REDACTED:8-digits","hashValue":"abc"}'


def test_redacts_multiple_lengths():
    raw = "before 12345678 and 1234567890 after"
    assert redact_account_numbers(raw) == "before REDACTED:8-digits and REDACTED:10-digits after"


def test_leaves_shorter_digit_runs():
    raw = '{"quantity":100}'
    assert redact_account_numbers(raw) == '{"quantity":100}'
