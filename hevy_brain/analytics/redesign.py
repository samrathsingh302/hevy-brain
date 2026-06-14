"""Current-programme snapshot (the `guide redesign` analytics).

A redesign starts from what the athlete is *actually* running: the split
(which workouts, how often, hitting which muscle groups), the weekly set and
volume distribution per muscle group, imbalances, and plateaus. Everything is
computed over the window ending at the LAST workout — never at today — so a
training lapse can not blank the picture a redesign must be anchored to.
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from . import patterns, stats
from .comeback import pre_lapse_baselines

# Groups a programme can plausibly target; anything standard with zero sets
# in the window is reported as untrained.
STANDARD_GROUPS = ("chest", "back", "shoulders", "biceps", "triceps", "legs", "core")


def split_summary(
    window: list[dict[str, Any]],
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
    group_limit: int = 3,
) -> list[dict[str, Any]]:
    """Describe the split: per workout title, sessions and top muscle groups.

    Hevy stamps a workout with its routine's title, so grouping by title
    recovers the split the athlete is actually running.
    """
    by_title: dict[str, dict[str, Any]] = {}
    for record in window:
        entry = by_title.setdefault(
            record["title"], {"title": record["title"], "sessions": 0, "_volumes": {}}
        )
        entry["sessions"] += 1
        for exercise in record["exercises"]:
            group = patterns.muscle_group(
                exercise["title"], exercise["template_id"], templates, overrides
            )
            entry["_volumes"][group] = (
                entry["_volumes"].get(group, 0.0) + exercise["volume_kg"]
            )
    summary = []
    for entry in by_title.values():
        ranked = sorted(entry["_volumes"].items(), key=lambda kv: kv[1], reverse=True)
        summary.append(
            {
                "title": entry["title"],
                "sessions": entry["sessions"],
                "groups": [group for group, _ in ranked[:group_limit]],
            }
        )
    summary.sort(key=lambda e: (-e["sessions"], e["title"]))
    return summary


def weekly_sets_by_group(
    window: list[dict[str, Any]],
    weeks: int,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, float]:
    """Average working sets per muscle group per week — the programming currency.

    Warm-up sets do not count as working sets (the redesign's volume targets
    would otherwise be anchored to an inflated number).
    """
    sets: dict[str, float] = {}
    for record in window:
        for exercise in record["exercises"]:
            working = sum(1 for s in exercise["sets"] if s.get("type") != "warmup")
            if not working:
                continue
            group = patterns.muscle_group(
                exercise["title"], exercise["template_id"], templates, overrides
            )
            sets[group] = sets.get(group, 0.0) + working
    if weeks:
        sets = {group: count / weeks for group, count in sets.items()}
    return dict(sorted(sets.items(), key=lambda kv: kv[1], reverse=True))


def classify_push_pull(ratio: float | None, low: float, high: float) -> str | None:
    """Label a push/pull volume ratio against the configured balance band."""
    if ratio is None:
        return None
    if ratio > high:
        return "push-heavy"
    if ratio < low:
        return "pull-heavy"
    return "balanced"


def training_snapshot(
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    *,
    weeks: int = 8,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
    plateau_weeks: int = 4,
    push_pull_low: float = 0.8,
    push_pull_high: float = 1.25,
) -> dict[str, Any] | None:
    """Build the full current-programme picture a redesign is grounded in.

    Builds on the baseline window math (window ends at the last workout) and
    adds split, weekly sets per group, balance flags, untrained groups, and
    plateaus — anchored at the window end so a lapse never hides them.
    """
    if not records:
        return None
    snapshot = pre_lapse_baselines(
        records, histories, weeks=weeks, templates=templates, overrides=overrides
    )
    window = stats.records_in_range(
        records,
        snapshot["window_start"],
        snapshot["window_end"] + timedelta(days=1),
    )

    # With less history than the window, dividing by the configured weeks
    # would dilute every weekly rate — divide by the weeks actually covered.
    first_date = records[0]["start_time"].date()
    covered_days = (
        snapshot["window_end"] - max(snapshot["window_start"], first_date)
    ).days + 1
    effective_weeks = min(weeks, math.ceil(covered_days / 7)) or 1
    snapshot["effective_weeks"] = effective_weeks
    if effective_weeks != weeks:
        snapshot["sessions_per_week"] = snapshot["sessions"] / effective_weeks
        snapshot["weekly_volume_kg"] = snapshot["volume_kg"] / effective_weeks

    snapshot["split"] = split_summary(window, templates, overrides)
    sets = weekly_sets_by_group(window, effective_weeks, templates, overrides)
    snapshot["weekly_sets_by_group"] = sets
    snapshot["untrained_groups"] = [
        group for group in STANDARD_GROUPS if group not in sets
    ]

    ratio = patterns.push_pull_ratio(snapshot["volume_by_group"])
    snapshot["push_pull_ratio"] = ratio
    snapshot["push_pull_flag"] = classify_push_pull(
        ratio, push_pull_low, push_pull_high
    )

    # Anchor plateau detection at the window end: with a lapse, "recent
    # sessions before today" is empty and every plateau would vanish.
    snapshot["plateaus"] = patterns.detect_plateaus(
        histories, snapshot["window_end"] + timedelta(days=1), plateau_weeks
    )
    return snapshot
