"""Central Europe/London civil-day clock.

Hevy returns workout timestamps in UTC (``...+00:00``). Historically the app's
notion of "today" was ``datetime.now(tz=UTC).date()`` — which lands a session
logged just after local midnight during British Summer Time on the *previous*
calendar day (00:30 BST == 23:30 UTC). Anything that asks "what civil day is
it?" must resolve against Europe/London instead; this module is the single
place that owns the zone.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")


def to_london(instant: datetime) -> datetime:
    """Convert an ``instant`` to a Europe/London-aware datetime.

    A naive datetime is assumed to be UTC (how Hevy timestamps arrive in the
    cache); an aware one is converted from its own offset. The instant is
    unchanged — only its wall-clock representation becomes London's, so a
    session logged at 21:18 UTC reads as 22:18 during BST.
    """
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    return instant.astimezone(LONDON)


def civil_day(instant: datetime) -> date:
    """Return the Europe/London calendar day an ``instant`` falls on."""
    return to_london(instant).date()


def now_london() -> datetime:
    """Return the current instant as a Europe/London-aware datetime."""
    return datetime.now(tz=LONDON)


def today_london() -> date:
    """Return today's civil date in Europe/London (the app's 'today')."""
    return civil_day(datetime.now(tz=UTC))
