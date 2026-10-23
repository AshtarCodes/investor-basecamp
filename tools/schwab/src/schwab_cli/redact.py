import re

_ACCOUNT_NUMBER = re.compile(r"\b(\d{8,12})\b")


def redact_account_numbers(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        n = len(match.group(1))
        return f"REDACTED:{n}-digits"

    return _ACCOUNT_NUMBER.sub(repl, text)
