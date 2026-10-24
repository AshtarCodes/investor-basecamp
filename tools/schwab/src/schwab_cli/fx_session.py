from datetime import datetime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def is_fx_market_open(at: datetime) -> bool:
    """FX spot is closed roughly Fri 17:00 – Sun 17:00 America/New_York."""
    local = at.astimezone(NY) if at.tzinfo else at.replace(tzinfo=NY)
    weekday = local.weekday()
    seconds = local.hour * 3600 + local.minute * 60 + local.second
    close_at = 17 * 3600

    if weekday == 5:
        return False
    if weekday == 6 and seconds < close_at:
        return False
    if weekday == 4 and seconds >= close_at:
        return False
    return True
