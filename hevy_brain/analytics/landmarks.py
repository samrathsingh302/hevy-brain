"""Volume-landmark check (S6): recent weekly sets/group vs MEV/MAV/MRV bands.

This is a **general guideline**, not personalised or medical advice and not a
cited claim (the knowledge corpus carries no programming claims — that gap is
surfaced honestly elsewhere). The landmark bands are the *user's* to own and
live, editable, in ``config.toml``; the defaults are sane published general
ranges (working sets per muscle group per week), nothing authoritative.

The recent weekly sets/group are computed over a window **anchored at the last
workout, never at today** (mirroring the redesign snapshot), so a training lapse
never blanks the picture into a misleading "everything below MEV". When the
account is actually lapsed (no recent training) the check degrades honestly to a
single "no recent training" line rather than classifying stale numbers.

All arithmetic is over cached records, so a rebuild over unchanged data with the
same ``today`` is byte-identical (idempotency fence).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import redesign, stats

# How recent the last workout must be for the bands to be assessed at all. Past
# this the account is treated as lapsed and the check degrades to an honest "no
# recent training" line — matching the deload heuristic's ~2-week recency gate.
RECENT_DAYS = 14

# The group classification ``muscle_group`` falls back to when nothing matches.
# It is never a real training target, so it is always excluded from the check.
_EXCLUDED_GROUP = "other"


def _classify(sets_per_week: float, band: dict[str, float]) -> str:
    """Label one group's weekly sets against its MEV/MAV/MRV band.

    Bands are read inclusively at the lower edge: a group sitting exactly on its
    MEV reads as ``MEV-MAV`` (maintenance/growth), not ``below MEV``.
    """
    if sets_per_week < band["mev"]:
        return "below MEV"
    if sets_per_week < band["mav"]:
        return "MEV-MAV (maintenance->growth)"
    if sets_per_week < band["mrv"]:
        return "MAV-MRV (productive)"
    return "above MRV (high)"


def landmark_status(
    records: list[dict[str, Any]],
    today: date,
    bands: dict[str, dict[str, float]],
    *,
    landmark_weeks: int,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Classify recent weekly sets/group against the configured landmark bands.

    Returns ``{"lapsed": False, "rows": [...]}`` where each row is
    ``{"group", "sets_per_week", "status", "band"}`` for every *present* group
    that has a configured band (``other`` is always excluded, and any present
    group with no band is skipped — never crashed, never invented). The window
    is anchored at the last workout and the weekly rate is divided by the number
    of distinct trained ISO weeks actually covered, clamped to
    ``[1, landmark_weeks]``, so short or sparse history is not diluted and a
    mid-week window straddling an extra ISO week does not deflate the rate.

    Degrades honestly to ``{"lapsed": True, ...}`` (no rows worth trusting) when:
    the history is empty, the bands are unconfigured, the last workout is more
    than ``RECENT_DAYS`` before ``today`` (a lapse) or after ``today`` (a
    backdated rebuild), or the anchored window holds no records. Returns ``None``
    only when the check is effectively disabled (``landmark_weeks <= 0``).
    """
    if landmark_weeks <= 0:
        return None
    if not records or not bands:
        return {"lapsed": True, "rows": []}

    last_date = records[-1]["start_time"].date()
    if not (0 <= (today - last_date).days <= RECENT_DAYS):
        return {"lapsed": True, "rows": []}  # lapsed, or future-dated

    window_start = last_date - timedelta(days=landmark_weeks * 7 - 1)
    window = stats.records_in_range(
        records, window_start, last_date + timedelta(days=1)
    )
    if not window:
        return {"lapsed": True, "rows": []}

    # weekly_sets_by_group divides by the weeks passed, so dividing by the
    # configured constant would dilute a short window — divide by the distinct
    # trained ISO weeks actually covered instead (>= 1). Cap at landmark_weeks:
    # a 4-week window anchored mid-week spans 28 days and can straddle 5 distinct
    # ISO weeks, which would otherwise over-count the divisor and deflate the
    # rate by ~20% (mirrors redesign.py's ``min(weeks, ...)`` cap).
    trained_weeks = {stats.week_start(r["start_time"].date()) for r in window}
    effective_weeks = max(1, min(landmark_weeks, len(trained_weeks)))
    weekly = redesign.weekly_sets_by_group(
        window, effective_weeks, templates, overrides
    )

    rows: list[dict[str, Any]] = []
    for group, sets_per_week in weekly.items():
        if group == _EXCLUDED_GROUP:
            continue
        band = bands.get(group)
        if band is None:
            continue  # present but unconfigured -> skip, never invent a band
        rows.append(
            {
                "group": group,
                "sets_per_week": sets_per_week,
                "status": _classify(sets_per_week, band),
                "band": band,
            }
        )
    # Stable, input-independent order: descending sets, then group name.
    rows.sort(key=lambda r: (-r["sets_per_week"], r["group"]))
    return {"lapsed": False, "rows": rows, "effective_weeks": effective_weeks}


def default_bands() -> dict[str, dict[str, float]]:
    """Sane published general volume-landmark defaults (sets/muscle/week).

    These are widely-circulated general-training-science ranges, **not** cited
    claims and **not** authoritative — they are the starting point the user edits
    in ``config.toml``. Used as the ``[landmarks]`` default so a no-config run
    still shows the table.
    """
    return {
        "chest": {"mev": 8.0, "mav": 14.0, "mrv": 22.0},
        "back": {"mev": 10.0, "mav": 16.0, "mrv": 25.0},
        "shoulders": {"mev": 8.0, "mav": 16.0, "mrv": 26.0},
        "biceps": {"mev": 8.0, "mav": 14.0, "mrv": 26.0},
        "triceps": {"mev": 6.0, "mav": 12.0, "mrv": 18.0},
        "legs": {"mev": 8.0, "mav": 16.0, "mrv": 25.0},
        "core": {"mev": 0.0, "mav": 12.0, "mrv": 25.0},
    }
