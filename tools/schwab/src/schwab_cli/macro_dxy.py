from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from schwab_cli.http_client import schwab_get
from schwab_cli.usdx import (
    UsdxQuoteError,
    build_usdx_payload,
    parse_leg_quotes,
    parse_schwab_quotes_json,
    usdx_quotes_path,
)


def run_macro_dxy(*, stdout: bool = True) -> dict:
    fetched_at = datetime.now(tz=UTC)
    response = schwab_get(usdx_quotes_path())
    if response.status_code != 200:
        msg = f"Schwab quotes HTTP {response.status_code}: {response.text[:500]}"
        raise UsdxQuoteError(msg)

    body = parse_schwab_quotes_json(response.text)
    legs = parse_leg_quotes(body)
    payload = build_usdx_payload(legs, fetched_at=fetched_at)

    if stdout:
        sys.stdout.write(json.dumps(payload, indent=2))
        sys.stdout.write("\n")

    return payload
