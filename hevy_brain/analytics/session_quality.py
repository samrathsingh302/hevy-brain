"""Session-quality patterns (A4): when you train, RPE discipline, duration.

All derived offline from cached records — no new data, no network. Surfaced as
a lightweight "Session quality" block on the Dashboard.
"""

from __future__ import annotations

from statistics import median
from typing import Any

# Hour-of-day buckets. Times come from the workout's recorded ``start_time``
# (tz-aware as Hevy stored it — effectively UTC; a UK user training in summer
# logs ~1h earlier in UTC than the local civil clock). Good enough for the
# coarse "morning vs evening" habit it reports; documented so the ~1h is known.
_PARTS: tuple[tuple[str, int, int], ...] = (
    ("Early morning", 5, 8),
    ("Morning", 8, 12),
    ("Afternoon", 12, 17),
    ("Evening", 17, 21),
    ("Night", 21, 5),  # wraps past midnight
)

_DEFAULT_RECENT_N = 10


def part_of_day(hour: int) -> str:
    """Map an hour (0-23) to a named part of the day."""
    for name, start, end in _PARTS:
        if start < end:
            if start <= hour < end:
                return name
        elif hour >= start or hour < end:  # the midnight-wrapping bucket
            return name
    return "Night"


def time_of_day_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Workout counts per part of day.

    Ordered by time of day (``_PARTS`` order), empty buckets omitted so the
    Dashboard only lists parts that actually occur.
    """
    counts = dict.fromkeys((name for name, _, _ in _PARTS), 0)
    for record in records:
        counts[part_of_day(record["start_time"].hour)] += 1
    return {name: counts[name] for name, _, _ in _PARTS if counts[name]}


def rpe_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    """RPE logging coverage over **working** sets (warm-ups excluded).

    Returns ``{working_sets, rpe_sets, coverage}`` where ``coverage`` is a
    fraction in [0, 1], or ``None`` when there are no working sets to judge.
    """
    working = 0
    with_rpe = 0
    for record in records:
        for exercise in record["exercises"]:
            for s in exercise["sets"]:
                if s.get("type") == "warmup":
                    continue
                working += 1
                if s.get("rpe") is not None:
                    with_rpe += 1
    return {
        "working_sets": working,
        "rpe_sets": with_rpe,
        "coverage": (with_rpe / working) if working else None,
    }


def duration_summary(
    records: list[dict[str, Any]], recent_n: int = _DEFAULT_RECENT_N
) -> dict[str, Any]:
    """Session-duration stats over sessions that recorded an end time.

    ``records`` are chronologically sorted (``build_records``), so the duration
    list keeps that order; ``recent_avg`` vs ``prior_avg`` (last ``recent_n``
    sessions vs the ``recent_n`` before them) gives a simple trend. Sessions
    with no duration (missing end time → ``duration_seconds`` 0) are excluded so
    a missing end never reads as a 0-minute session.
    """
    durations = [
        r["duration_seconds"] / 60 for r in records if r["duration_seconds"] > 0
    ]
    if not durations:
        return {"sessions": 0}
    recent = durations[-recent_n:]
    prior = durations[-2 * recent_n : -recent_n]
    return {
        "sessions": len(durations),
        "avg_min": sum(durations) / len(durations),
        "median_min": median(durations),
        "longest_min": max(durations),
        "shortest_min": min(durations),
        "recent_avg_min": sum(recent) / len(recent),
        "prior_avg_min": (sum(prior) / len(prior)) if prior else None,
    }


def session_quality(
    records: list[dict[str, Any]], recent_n: int = _DEFAULT_RECENT_N
) -> dict[str, Any]:
    """Roll up the three session-quality views for one record set."""
    return {
        "total_sessions": len(records),
        "time_of_day": time_of_day_counts(records),
        "rpe": rpe_coverage(records),
        "duration": duration_summary(records, recent_n),
    }
