"""Training pattern analysis: muscle balance, plateaus, overload tracking."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# Fallback keyword mapping used when the Hevy exercise template (which
# carries primary_muscle_group) is unavailable. First match wins.
_KEYWORD_GROUPS: list[tuple[str, str]] = [
    ("bench", "chest"),
    ("chest", "chest"),
    ("fly", "chest"),
    ("push up", "chest"),
    ("pushup", "chest"),
    ("dip", "chest"),
    ("row", "back"),
    ("pulldown", "back"),
    ("pull down", "back"),
    ("pull up", "back"),
    ("pullup", "back"),
    ("chin", "back"),
    ("lat ", "back"),
    ("shrug", "back"),
    ("deadlift", "back"),
    ("face pull", "shoulders"),
    ("shoulder", "shoulders"),
    ("overhead press", "shoulders"),
    ("ohp", "shoulders"),
    ("lateral raise", "shoulders"),
    ("front raise", "shoulders"),
    ("rear delt", "shoulders"),
    ("arnold", "shoulders"),
    ("curl", "biceps"),
    ("tricep", "triceps"),
    ("pushdown", "triceps"),
    ("skull", "triceps"),
    ("extension", "triceps"),
    ("squat", "legs"),
    ("leg", "legs"),
    ("lunge", "legs"),
    ("calf", "legs"),
    ("hip thrust", "legs"),
    ("glute", "legs"),
    ("rdl", "legs"),
    ("hamstring", "legs"),
    ("crunch", "core"),
    ("plank", "core"),
    ("ab ", "core"),
    ("sit up", "core"),
    ("russian twist", "core"),
]

# Hevy template muscle groups → our coarse buckets.
_TEMPLATE_GROUPS = {
    "chest": "chest",
    "lats": "back",
    "upper_back": "back",
    "lower_back": "back",
    "traps": "back",
    "shoulders": "shoulders",
    "biceps": "biceps",
    "triceps": "triceps",
    "forearms": "biceps",
    "quadriceps": "legs",
    "hamstrings": "legs",
    "glutes": "legs",
    "calves": "legs",
    "adductors": "legs",
    "abductors": "legs",
    "abdominals": "core",
    "obliques": "core",
}

PUSH_GROUPS = {"chest", "shoulders", "triceps"}
PULL_GROUPS = {"back", "biceps"}


def muscle_group(
    title: str,
    template_id: str = "",
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
) -> str:
    """Classify an exercise into a coarse muscle group."""
    if overrides:
        for needle, group in overrides.items():
            if needle.lower() in title.lower():
                return group
    if templates and template_id in templates:
        primary = (templates[template_id].get("primary_muscle_group") or "").lower()
        if primary in _TEMPLATE_GROUPS:
            return _TEMPLATE_GROUPS[primary]
    lowered = f" {title.lower()} "
    for needle, group in _KEYWORD_GROUPS:
        if needle in lowered:
            return group
    return "other"


def volume_by_group(
    records: list[dict[str, Any]],
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, float]:
    """Total volume (kg) per muscle group across the given records."""
    volumes: dict[str, float] = {}
    for record in records:
        for exercise in record["exercises"]:
            group = muscle_group(
                exercise["title"], exercise["template_id"], templates, overrides
            )
            volumes[group] = volumes.get(group, 0.0) + exercise["volume_kg"]
    # Descending volume; group name breaks exact ties so the order never
    # depends on input/iteration order (keeps generated notes deterministic).
    return dict(sorted(volumes.items(), key=lambda kv: (-kv[1], kv[0])))


def push_pull_ratio(volumes: dict[str, float]) -> float | None:
    """Push volume / pull volume, or None if pull volume is zero."""
    push = sum(v for g, v in volumes.items() if g in PUSH_GROUPS)
    pull = sum(v for g, v in volumes.items() if g in PULL_GROUPS)
    if pull <= 0:
        return None
    return push / pull


def detect_plateaus(
    histories: dict[str, dict[str, Any]],
    today: date,
    plateau_weeks: int = 4,
) -> list[dict[str, Any]]:
    """Exercises trained regularly whose estimated 1RM has stopped improving.

    An exercise plateaus when it has at least `plateau_weeks` sessions in the
    recent window (last `plateau_weeks` weeks) and the best estimated 1RM in
    that window does not exceed the best from the preceding window.
    """
    plateaus: list[dict[str, Any]] = []
    recent_start = today - timedelta(weeks=plateau_weeks)
    prior_start = today - timedelta(weeks=plateau_weeks * 2)
    for history in histories.values():
        recent = [s for s in history["sessions"] if s["date"] >= recent_start]
        prior = [
            s for s in history["sessions"] if prior_start <= s["date"] < recent_start
        ]
        if len(recent) < plateau_weeks or not prior:
            continue
        best_recent = max(s["best_e1rm_kg"] for s in recent)
        best_prior = max(s["best_e1rm_kg"] for s in prior)
        if best_prior > 0 and best_recent <= best_prior:
            plateaus.append(
                {
                    "exercise": history["title"],
                    "best_recent_e1rm_kg": best_recent,
                    "best_prior_e1rm_kg": best_prior,
                    "recent_sessions": len(recent),
                }
            )
    return plateaus


def weekly_overload(records: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """Per-exercise volume delta: last 7 days vs the 7 days before that."""
    last_week_start = today - timedelta(days=7)
    prior_week_start = today - timedelta(days=14)
    last: dict[str, float] = {}
    prior: dict[str, float] = {}
    for record in records:
        workout_date = record["start_time"].date()
        if workout_date >= last_week_start:
            bucket = last
        elif workout_date >= prior_week_start:
            bucket = prior
        else:
            continue
        for exercise in record["exercises"]:
            title = exercise["title"]
            bucket[title] = bucket.get(title, 0.0) + exercise["volume_kg"]
    deltas: list[dict[str, Any]] = []
    for title in sorted(set(last) | set(prior)):
        last_volume = last.get(title, 0.0)
        prior_volume = prior.get(title, 0.0)
        if last_volume == 0 and prior_volume == 0:
            continue
        deltas.append(
            {
                "exercise": title,
                "last_week_kg": last_volume,
                "prior_week_kg": prior_volume,
                "delta_kg": last_volume - prior_volume,
            }
        )
    deltas.sort(key=lambda d: d["delta_kg"])
    return deltas
