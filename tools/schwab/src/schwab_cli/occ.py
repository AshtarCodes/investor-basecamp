import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

# Root padded to six characters, YYMMDD, C or P, then the strike in thousandths over eight digits.
_OCC = re.compile(r"^(?P<root>[A-Z]{1,5}[0-9]?) *(?P<ymd>\d{6})(?P<right>[CP])(?P<strike>\d{8})$")
_OCC_LENGTH = 21


@dataclass(frozen=True)
class OccSymbol:
    symbol: str
    root: str
    expiry: date
    strike: float
    right: Literal["call", "put"]


def parse_occ(symbol: str) -> OccSymbol:
    """Parse a 21-character OCC symbol, as Schwab prints it, with the root's padding stripped."""
    match = _OCC.fullmatch(symbol) if len(symbol) == _OCC_LENGTH else None
    if match is None:
        msg = f"not an OCC option symbol (root padded to 6, YYMMDD, C or P, 8-digit strike): {symbol!r}"
        raise ValueError(msg)
    ymd = match["ymd"]
    try:
        expiry = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:]))
    except ValueError as error:
        msg = f"OCC symbol has an impossible expiry date {ymd!r}: {symbol!r}"
        raise ValueError(msg) from error
    return OccSymbol(
        symbol=symbol,
        root=match["root"],
        expiry=expiry,
        strike=int(match["strike"]) / 1000,
        right="call" if match["right"] == "C" else "put",
    )
