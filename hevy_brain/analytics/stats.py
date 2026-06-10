"""Aggregate training statistics (ported from the HA sensor math)."""

from __future__ import annotations

from datetime import date, timedelta
from itertools import pairwise
from typing import Any


def compute_streaks(workout_dates: set[date], today: date) -> tuple[int, int]:
    """Compute (current_streak_days, longest_streak_days) from a set of dates."""
    if not workout_dates:
        return 0, 0

    sorted_dates = sorted(workout_dates, reverse=True)

    current = 0
    if sorted_dates[0] in (today, today - timedelta(days=1)):
        cursor = sorted_dates[0]
        current = 1
        for d in sorted_dates[1:]:
            if d == cursor - timedelta(days=1):
                cursor = d
                current += 1
            else:
                break

    longest = 1
    run = 1
    for prev, nxt in pairwise(sorted_dates):
        if prev - nxt == timedelta(days=1):
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    return current, longest


def week_start(day: date) -> date:
    """Monday of the ISO week containing `day`."""
    return day - timedelta(days=day.weekday())


def compute_aggregates(records: list[dict[str, Any]], today: date) -> dict[str, Any]:
    """Period aggregates over processed workout records."""
    agg: dict[str, Any] = {
        "total_workouts": len(records),
        "total_volume_kg": 0.0,
        "today_count": 0,
        "week_count": 0,
        "month_count": 0,
        "year_count": 0,
        "volume_today_kg": 0.0,
        "volume_week_kg": 0.0,
        "volume_month_kg": 0.0,
        "volume_year_kg": 0.0,
        "duration_week_min": 0.0,
        "duration_month_min": 0.0,
        "workout_dates": set(),
    }
    for record in records:
        workout_date = record["start_time"].date()
        volume = record["volume_kg"]
        duration_min = record["duration_seconds"] / 60
        agg["total_volume_kg"] += volume
        agg["workout_dates"].add(workout_date)
        if workout_date == today:
            agg["today_count"] += 1
            agg["volume_today_kg"] += volume
        if (today - workout_date).days < 7:
            agg["week_count"] += 1
            agg["volume_week_kg"] += volume
            agg["duration_week_min"] += duration_min
        if (workout_date.year, workout_date.month) == (today.year, today.month):
            agg["month_count"] += 1
            agg["volume_month_kg"] += volume
            agg["duration_month_min"] += duration_min
        if workout_date.year == today.year:
            agg["year_count"] += 1
            agg["volume_year_kg"] += volume

    current, longest = compute_streaks(agg["workout_dates"], today)
    agg["current_streak_days"] = current
    agg["longest_streak_days"] = longest
    return agg


def weekly_series(records: list[dict[str, Any]]) -> dict[date, dict[str, Any]]:
    """Per-ISO-week totals: sessions, volume, duration."""
    series: dict[date, dict[str, Any]] = {}
    for record in records:
        bucket = week_start(record["start_time"].date())
        entry = series.setdefault(
            bucket, {"sessions": 0, "volume_kg": 0.0, "duration_min": 0.0}
        )
        entry["sessions"] += 1
        entry["volume_kg"] += record["volume_kg"]
        entry["duration_min"] += record["duration_seconds"] / 60
    return dict(sorted(series.items()))


def records_in_range(
    records: list[dict[str, Any]], start: date, end: date
) -> list[dict[str, Any]]:
    """Return records whose date is in [start, end)."""
    return [r for r in records if start <= r["start_time"].date() < end]
