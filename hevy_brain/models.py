"""Turn raw Hevy API workout payloads into processed records."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def set_volume_kg(workout_set: dict[str, Any]) -> float:
    """Return volume (weight * reps) for a single set, treating None as 0."""
    weight = workout_set.get("weight_kg") or 0
    reps = workout_set.get("reps") or 0
    return float(weight) * float(reps)


def is_warmup(workout_set: dict[str, Any]) -> bool:
    """Return True if a set is a warm-up, in either shape the app ingests.

    Cached workout sets carry the set type under ``type`` (Hevy's workout
    payload, passed through verbatim); the ``exercise_history`` endpoint used by
    the reconcile check tags the same concept under ``set_type``. The two keys
    are disjoint per shape, so testing both lets a single predicate guard every
    working-set filter — the two spellings can no longer drift out of step,
    which is the bug that let warm-ups inflate estimated 1RM (``best_e1rm_kg``).
    """
    return (
        workout_set.get("type") == "warmup"
        or workout_set.get("set_type") == "warmup"
    )


def parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp ('Z' suffix included), or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def build_workout_record(workout: dict[str, Any]) -> dict[str, Any]:
    """Build a processed record from a raw API workout payload."""
    start_time = parse_iso(workout.get("start_time"))
    end_time = parse_iso(workout.get("end_time"))
    duration_seconds = 0.0
    if start_time and end_time:
        duration_seconds = max(0.0, (end_time - start_time).total_seconds())

    exercises: list[dict[str, Any]] = []
    volume_kg = 0.0
    total_reps = 0
    for exercise in workout.get("exercises", []):
        sets = exercise.get("sets", [])
        exercise_volume = sum(set_volume_kg(s) for s in sets)
        exercise_reps = sum(s.get("reps") or 0 for s in sets)
        volume_kg += exercise_volume
        total_reps += exercise_reps
        exercises.append(
            {
                "title": exercise.get("title", "Unknown Exercise"),
                "template_id": exercise.get("exercise_template_id", ""),
                "notes": exercise.get("notes"),
                "superset_id": exercise.get("superset_id"),
                "sets": sets,
                "set_count": len(sets),
                "total_reps": exercise_reps,
                "volume_kg": exercise_volume,
                "max_weight_kg": max(
                    (s.get("weight_kg") or 0 for s in sets), default=0
                ),
            }
        )

    return {
        "id": workout["id"],
        "title": workout.get("title") or "Workout",
        "description": workout.get("description"),
        "is_private": bool(workout.get("is_private", False)),
        "start_time": start_time,
        "end_time": end_time,
        "updated_at": workout.get("updated_at"),
        "duration_seconds": duration_seconds,
        "exercises": exercises,
        "volume_kg": volume_kg,
        "total_reps": total_reps,
        "exercise_count": len(exercises),
    }


def build_records(raw_workouts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Build records for all cached workouts, sorted chronologically.

    Workouts without a parseable start_time are dropped (they cannot be
    placed on a timeline).
    """
    records = [build_workout_record(w) for w in raw_workouts.values()]
    records = [r for r in records if r["start_time"] is not None]
    records.sort(key=lambda r: r["start_time"])
    return records
