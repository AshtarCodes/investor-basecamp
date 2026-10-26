from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from pricing_engine import settlement_instant
from pricing_engine.settlement import NEW_YORK

# A date with no time of day means the close.
DATE_AS_OF_TIME = time(16, 0)


def days_between(start: datetime, end: datetime) -> float:
    """Elapsed calendar days, fractions allowed, counted in UTC so daylight saving is right."""
    return (end - start).total_seconds() / 86400


def _parse_as_of(text: str) -> datetime:
    try:
        if len(text) == 10:
            return datetime.combine(date.fromisoformat(text), DATE_AS_OF_TIME, tzinfo=NEW_YORK)
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        msg = f"--as-of {text!r} is not a date (YYYY-MM-DD) or an ISO datetime with an offset"
        raise ValueError(msg) from error
    if parsed.tzinfo is None:
        msg = f"--as-of {text!r} has no UTC offset; use a date, or e.g. 2026-06-30T10:00:00-04:00"
        raise ValueError(msg)
    return parsed


def resolve_instant(
    *,
    mode: Literal["theoretical", "sell"],
    root: str,
    expiry: date,
    now: datetime,
    as_of: str | None,
    dte: float | None,
    offline: bool,
) -> datetime:
    """The valuation instant (`theoretical`) or exit instant (`sell`) as one aware datetime.

    `--dte` wins over `--as-of`. A live run takes nothing before now, and a live `theoretical`
    takes no date at all: use `--dte`, `sell`, or `--offline`.
    """
    settlement = settlement_instant(root, expiry).astimezone(UTC)  # elapsed time, not wall clock
    if dte is not None:
        if dte < 0:
            raise ValueError("--dte must not be negative")
        instant = settlement - timedelta(days=dte)
    elif as_of is not None:
        instant = _parse_as_of(as_of).astimezone(UTC)
        if mode == "theoretical" and not offline:
            raise ValueError(
                "a live theoretical value is for now: use --dte for a time stress, "
                "--mode sell for a dated exit, or --offline for a past point in time"
            )
    else:
        instant = now.astimezone(UTC)
    if instant >= settlement:
        msg = f"the {_name(mode)} instant {instant.isoformat()} is at or after the Settlement instant {settlement.isoformat()}"
        raise ValueError(msg)
    if not offline and instant < now:
        msg = (
            f"the {_name(mode)} instant {instant.isoformat()} is before now "
            "(a past --as-of, or a --dte longer than the contract's remaining life): use --offline"
        )
        raise ValueError(msg)
    return instant


def _name(mode: str) -> str:
    return "valuation" if mode == "theoretical" else "exit"
