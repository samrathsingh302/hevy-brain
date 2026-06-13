"""Lapse detection and pre-lapse baselines (the `guide return` analytics).

A lapse is a gap between today and the last logged workout. Baselines are
computed over the window of training that *preceded* the lapse, so a comeback
plan can be anchored to what the athlete was actually doing — weekly volume,
session frequency, top sets and estimated 1RMs — rather than to guesses.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import patterns, stats


def lapse_status(records: list[dict[str, Any]], today: date) -> dict[str, Any] | None:
    """Days since the last logged workout, or None with an empty history."""
    if not records:
        return None
    last_date = records[-1]["start_time"].date()
    return {
        "last_workout_date": last_date,
        "last_workout_title": records[-1]["title"],
        "days_since": (today - last_date).days,
    }


def lapse_nudge(
    records: list[dict[str, Any]],
    today: date,
    *,
    nudge_days: int,
    lapse_days: int,
) -> dict[str, Any] | None:
    """Lapse-nudge facts when the quiet streak warrants surfacing one, else None.

    Returns the ``lapse_status`` fields plus a ``severity``: ``"lapse"`` once the
    gap reaches ``lapse_days`` (the ``guide return`` threshold, where a comeback
    plan is the right call), otherwise ``"nudge"``. None below ``nudge_days``,
    with an empty history, or when nudging is disabled (``nudge_days <= 0``).
    """
    if nudge_days <= 0:
        return None
    status = lapse_status(records, today)
    if status is None or status["days_since"] < nudge_days:
        return None
    severity = "lapse" if status["days_since"] >= lapse_days else "nudge"
    return {**status, "severity": severity}


def pre_lapse_baselines(
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    *,
    weeks: int = 4,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
    top_limit: int = 8,
) -> dict[str, Any]:
    """Baselines over the `weeks`-week window ending at the last workout.

    The window covers exactly ``weeks * 7`` days, inclusive of the last
    workout's date, so a lapse of any length never dilutes the numbers.
    """
    window_end = records[-1]["start_time"].date()
    window_start = window_end - timedelta(days=weeks * 7 - 1)
    window = stats.records_in_range(
        records, window_start, window_end + timedelta(days=1)
    )

    total_volume = sum(r["volume_kg"] for r in window)
    by_exercise: dict[str, dict[str, Any]] = {}
    for record in window:
        for exercise in record["exercises"]:
            title = exercise["title"]
            entry = by_exercise.setdefault(
                title,
                {
                    "title": title,
                    "sessions": 0,
                    "volume_kg": 0.0,
                    "top_weight_kg": 0.0,
                    "window_e1rm_kg": 0.0,
                },
            )
            entry["sessions"] += 1
            entry["volume_kg"] += exercise["volume_kg"]
            entry["top_weight_kg"] = max(
                entry["top_weight_kg"], exercise["max_weight_kg"]
            )

    for title, entry in by_exercise.items():
        history = histories.get(title)
        if history:
            window_sessions = [
                s for s in history["sessions"] if s["date"] >= window_start
            ]
            entry["window_e1rm_kg"] = max(
                (s["best_e1rm_kg"] for s in window_sessions), default=0.0
            )
            entry["all_time_e1rm_kg"] = history["best_e1rm_kg"]
        else:
            entry["all_time_e1rm_kg"] = 0.0

    top_exercises = sorted(
        by_exercise.values(), key=lambda e: e["volume_kg"], reverse=True
    )[:top_limit]

    return {
        "window_start": window_start,
        "window_end": window_end,
        "weeks": weeks,
        "sessions": len(window),
        "sessions_per_week": len(window) / weeks if weeks else 0.0,
        "volume_kg": total_volume,
        "weekly_volume_kg": total_volume / weeks if weeks else 0.0,
        "volume_by_group": patterns.volume_by_group(window, templates, overrides),
        "top_exercises": top_exercises,
        "workout_titles": sorted({r["title"] for r in window}),
    }
