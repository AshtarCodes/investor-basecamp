"""The Settlement instant: when a contract stops trading and settles (GLOSSARY.md)."""

import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")

PM_SETTLEMENT = time(16, 0)
AM_SETTLEMENT = time(9, 30)
# A cash dividend drops the spot as the market opens on its ex-date.
EX_DATE_DROP = time(9, 30)

# Index roots whose Settlement instant ADR 0001 pins down.
INDEX_SETTLEMENT = {
    "SPX": AM_SETTLEMENT,
    "SPXW": PM_SETTLEMENT,
    "XSP": PM_SETTLEMENT,
}

# Index roots that match the equity pattern but settle by rules this engine does not
# model yet. Pricing them at 16:00 would be a silent wrong answer, so they are errors.
UNSUPPORTED_INDEX_ROOTS = frozenset(
    {"NDX", "NDXP", "RUT", "RUTW", "XEO", "DJX", "OEX", "VIX", "VIXW", "XND", "MRUT"}
)

# An OCC equity or ETF root: up to five capitals, with a trailing digit on adjusted roots.
EQUITY_ROOT = re.compile(r"^[A-Z]{1,5}[0-9]?$")


class UnknownRootError(ValueError):
    """The OCC root has no known Settlement instant."""


def settlement_instant(root: str, expiry: date) -> datetime:
    """The timezone-aware Settlement instant of a contract with this OCC root and expiry date."""
    if root in INDEX_SETTLEMENT:
        settles_at = INDEX_SETTLEMENT[root]
    elif root in UNSUPPORTED_INDEX_ROOTS:
        raise UnknownRootError(f"no Settlement instant is modelled for index root {root!r}")
    elif EQUITY_ROOT.fullmatch(root):
        settles_at = PM_SETTLEMENT
    else:
        raise UnknownRootError(f"{root!r} is not an OCC root")
    return datetime.combine(expiry, settles_at, tzinfo=NEW_YORK)
