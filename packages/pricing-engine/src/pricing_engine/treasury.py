"""The risk-free rate for an expiry, from the Treasury.gov daily par yield curve (ADR 0001).

This is the only module in the engine that touches the network.
"""

import math
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from bisect import bisect_left
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from pydantic import Field

from pricing_engine.models import Sourced

CURVE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    "?data=daily_treasury_yield_curve&field_tdr_date_value_month={month}"
)
REQUEST_TIMEOUT_SECONDS = 15
CACHE_SECONDS = 24 * 3600
# Treasury.gov holds requests that carry a stock client's User-Agent (urllib's, curl's) for
# about 18 s and answers one that names itself in 0.2 s.
USER_AGENT = "investor-basecamp-pricing-engine"

# Quoted tenors in years, by the field name Treasury.gov uses. The `BC_30YEARDISPLAY` column
# repeats the 30-year yield and is left out.
TENORS = {
    "BC_1MONTH": 1 / 12,
    "BC_1_5MONTH": 1.5 / 12,
    "BC_2MONTH": 2 / 12,
    "BC_3MONTH": 3 / 12,
    "BC_4MONTH": 4 / 12,
    "BC_6MONTH": 6 / 12,
    "BC_1YEAR": 1.0,
    "BC_2YEAR": 2.0,
    "BC_3YEAR": 3.0,
    "BC_5YEAR": 5.0,
    "BC_7YEAR": 7.0,
    "BC_10YEAR": 10.0,
    "BC_20YEAR": 20.0,
    "BC_30YEAR": 30.0,
}


class TreasuryError(Exception):
    """The curve could not be fetched or read. The caller turns this into a fallback rate."""


class EmptyMonthError(TreasuryError):
    """The month's file has no entries, as in the first days of a month."""


@dataclass(frozen=True)
class YieldCurve:
    """One day's par yields, as percent bond-equivalent, at ascending tenors in years."""

    curve_date: date
    tenors: tuple[float, ...]
    par_yields: tuple[float, ...]

    def rate(self, years: float) -> float:
        """The continuous rate, as a decimal, at `years`: linear in tenor, flat past the ends."""
        rates = [2 * math.log(1 + y / 200) for y in self.par_yields]
        if years <= self.tenors[0]:
            return rates[0]
        if years >= self.tenors[-1]:
            return rates[-1]
        i = bisect_left(self.tenors, years)
        weight = (years - self.tenors[i - 1]) / (self.tenors[i] - self.tenors[i - 1])
        return rates[i - 1] + weight * (rates[i] - rates[i - 1])


def parse_curve(xml: str) -> YieldCurve:
    """The latest curve in one month's Treasury.gov XML."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as error:
        raise TreasuryError(f"unreadable Treasury XML: {error}") from error
    latest: tuple[date, dict[str, float]] | None = None
    for properties in root.iter():
        if not properties.tag.endswith("}properties"):
            continue
        fields = {re.sub(r"^\{.*\}", "", child.tag): (child.text or "") for child in properties}
        try:
            curve_date = date.fromisoformat(fields["NEW_DATE"][:10])
            yields = {name: float(fields[name]) for name in TENORS if fields.get(name)}
        except (KeyError, ValueError) as error:
            raise TreasuryError(f"unreadable Treasury entry: {error!r}") from error
        if latest is None or curve_date > latest[0]:
            latest = (curve_date, yields)
    if latest is None or not latest[1]:
        raise EmptyMonthError("no curve entries in the month")
    curve_date, yields = latest
    quoted = sorted((TENORS[name], y) for name, y in yields.items())
    return YieldCurve(
        curve_date=curve_date,
        tenors=tuple(t for t, _ in quoted),
        par_yields=tuple(y for _, y in quoted),
    )


class RateQuote(Sourced):
    """A continuous rate as a decimal, with its source. `curve_date` is null for the fallback."""

    curve_date: date | None = Field(default=None, alias="curveDate")


# Month as `YYYYMM` to that month's XML text.
Fetch = Callable[[str], str]


def fetch_month(month: str) -> str:
    """One month's XML from Treasury.gov. Raises OSError on a network failure."""
    request = urllib.request.Request(
        CURVE_URL.format(month=month), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


class TreasuryCurves:
    """Looks up rates, keeping each fetched month for a day in memory and, when `cache_dir` is
    given, on disk so a new process starts warm."""

    def __init__(
        self,
        fetch: Fetch = fetch_month,
        cache_dir: Path | None = None,
        now: Callable[[], float] = time.time,
    ):
        self._fetch = fetch
        self._cache_dir = cache_dir
        self._now = now
        self._curves: dict[str, tuple[float, YieldCurve]] = {}

    def rate(
        self, *, valuation_date: date, expiry: date, fallback_percent: float | None
    ) -> RateQuote:
        """The Treasury rate for the expiry.

        When the curve can't be had, `fallback_percent` (Schwab's chain `interestRate`) is used and
        flagged `schwab-chain-fallback`. With no fallback the TreasuryError propagates.
        """
        try:
            curve = self._latest_curve(valuation_date)
        except (TreasuryError, OSError) as error:
            if fallback_percent is None:
                raise TreasuryError(f"no Treasury curve and no fallback: {error}") from error
            return RateQuote(value=fallback_percent / 100, from_="schwab-chain-fallback")
        years = max((expiry - valuation_date).days, 0) / 365
        return RateQuote(value=curve.rate(years), from_="treasury-gov", curve_date=curve.curve_date)

    def _latest_curve(self, valuation_date: date) -> YieldCurve:
        this_month = valuation_date.replace(day=1)
        last_month = this_month - timedelta(days=1)
        try:
            return self._month_curve(this_month.strftime("%Y%m"))
        except EmptyMonthError:
            return self._month_curve(last_month.strftime("%Y%m"))

    def _month_curve(self, month: str) -> YieldCurve:
        now = self._now()
        held = self._curves.get(month)
        if held and now - held[0] < CACHE_SECONDS:
            return held[1]
        if (curve := self._read_disk(month, now)) is None:
            xml = self._fetch(month)
            curve = parse_curve(xml)
            self._write_disk(month, xml, now)
        self._curves[month] = (now, curve)
        return curve

    def _read_disk(self, month: str, now: float) -> YieldCurve | None:
        if self._cache_dir is None:
            return None
        path = self._cache_dir / f"treasury-{month}.xml"
        try:
            if now - path.stat().st_mtime >= CACHE_SECONDS:
                return None
            return parse_curve(path.read_text())
        except (OSError, TreasuryError):
            return None

    def _write_disk(self, month: str, xml: str, now: float) -> None:
        if self._cache_dir is None:
            return
        path = self._cache_dir / f"treasury-{month}.xml"
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(xml)
            os.utime(path, (now, now))
        except OSError:
            pass  # the disk cache is an optimisation
