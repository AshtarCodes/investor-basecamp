"""Replay the live fixtures behind `schwab_get` and the Treasury fetch, and nothing else."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from pricing_engine import TreasuryCurves

from schwab_cli.config import repo_root
from schwab_cli.http_client import SchwabResponse

FIXTURES = Path(__file__).parent / "fixtures" / "option_price"
TREASURY_FIXTURES = repo_root() / "packages" / "pricing-engine" / "tests" / "fixtures"

SYMBOLS = {
    "iren": "IREN  270115C00025000",
    "spy": "SPY   270115C00765000",
    "xsp": "XSP   261218C00768000",
}


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def quote_time(key: str) -> datetime:
    row = load(f"{key}_option_quote.json")[SYMBOLS[key]]
    return datetime.fromtimestamp(row["quote"]["quoteTime"] / 1000, tz=UTC)


def now_for(key: str) -> datetime:
    """One second after the quote, so the quote is fresh."""
    return quote_time(key) + timedelta(seconds=1)


class FakeSchwab:
    """A `get` that answers from the fixtures and records every path it was asked for."""

    def __init__(self, key: str, *, status: int = 200):
        self.key = key
        self.status = status
        self.paths: list[str] = []
        self.option_quote = load(f"{key}_option_quote.json")
        self.underlying_quote = load(f"{key}_underlying_quote.json")
        self.chain = load(f"{key}_chain.json")
        self.analytical = load(f"{key}_analytical.json")

    @property
    def option_row(self) -> dict:
        return self.option_quote[SYMBOLS[self.key]]

    @property
    def fundamental(self) -> dict:
        return next(iter(self.underlying_quote.values()))["fundamental"]

    def __call__(self, path: str) -> SchwabResponse:
        self.paths.append(path)
        query = parse_qs(urlparse(path).query)
        if self.status >= 400:
            return SchwabResponse(self.status, "{}", path)
        if "/chains" in path:
            body = self.analytical if query.get("strategy") == ["ANALYTICAL"] else self.chain
        elif unquote(query["symbols"][0]) in self.option_quote:
            body = self.option_quote
        else:
            body = self.underlying_quote
        return SchwabResponse(200, json.dumps(copy.deepcopy(body)), path)

    def analytical_query(self) -> dict[str, str]:
        path = next(p for p in self.paths if "strategy=ANALYTICAL" in p)
        return {k: v[0] for k, v in parse_qs(urlparse(path).query).items()}


def treasury_curves(*, fail: bool = False) -> TreasuryCurves:
    def fetch(month: str) -> str:
        if fail:
            raise OSError("offline")
        return (TREASURY_FIXTURES / f"treasury-{month}.xml").read_text()

    return TreasuryCurves(fetch=fetch)
