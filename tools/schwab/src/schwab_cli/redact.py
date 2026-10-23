import json
import re
from typing import Any

_ACCOUNT_NUMBER = re.compile(r"\b(\d{8})\b")


def _redact_value(obj: Any) -> Any:
    if isinstance(obj, dict):
        redacted: dict[str, Any] = {}
        for key, value in obj.items():
            if key == "accountNumber" and isinstance(value, str) and re.fullmatch(r"\d{8}", value):
                redacted[key] = "REDACTED:8-digits"
            else:
                redacted[key] = _redact_value(value)
        return redacted
    if isinstance(obj, list):
        return [_redact_value(item) for item in obj]
    return obj


def redact_account_numbers(text: str) -> str:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return _ACCOUNT_NUMBER.sub(lambda m: f"REDACTED:{len(m.group(1))}-digits", text)
    return json.dumps(_redact_value(parsed), separators=(",", ":"))
