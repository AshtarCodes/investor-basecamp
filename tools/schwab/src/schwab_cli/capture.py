import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from schwab_cli.config import captures_dir
from schwab_cli.http_client import SchwabResponse, schwab_get
from schwab_cli.redact import redact_account_numbers

_REMAINING_ACCOUNT_DIGITS = re.compile(r"\b\d{8,12}\b")


def _slug(label: str) -> str:
    return label.lower().replace(" ", "-")


def _write_capture(*, label: str, response: SchwabResponse) -> Path:
    captures_dir().mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = captures_dir() / f"{timestamp}_{_slug(label)}.json"
    body = redact_account_numbers(response.text)
    path.write_text(body, encoding="utf-8")
    print(f"{response.status_code} {path}")
    return path


def run_capture(*, option_symbol: str, equity_ticker: str) -> None:
    option_encoded = quote(option_symbol, safe="")
    equity_encoded = quote(equity_ticker, safe="")

    requests: list[tuple[str, str]] = [
        ("account numbers", "/trader/v1/accounts/accountNumbers"),
        ("accounts positions", "/trader/v1/accounts?fields=positions"),
        (
            "option quote",
            f"/marketdata/v1/quotes?symbols={option_encoded}",
        ),
        (
            "equity quote",
            f"/marketdata/v1/quotes?symbols={equity_encoded}",
        ),
        (
            "equity price history",
            "/marketdata/v1/pricehistory?"
            f"symbol={equity_encoded}"
            "&periodType=year&period=1&frequencyType=daily&frequency=1",
        ),
        (
            "option chain",
            "/marketdata/v1/chains?"
            f"symbol={equity_encoded}"
            "&contractType=ALL&includeUnderlyingQuote=true",
        ),
    ]

    for index, (label, path) in enumerate(requests):
        response = schwab_get(path)
        capture_path = _write_capture(label=label, response=response)
        if index == 0:
            body = capture_path.read_text(encoding="utf-8")
            if _REMAINING_ACCOUNT_DIGITS.search(body):
                print(
                    "Warning: account-number-shaped digits remain in the first "
                    f"capture ({capture_path.name}). Review before sharing.",
                    file=sys.stderr,
                )
