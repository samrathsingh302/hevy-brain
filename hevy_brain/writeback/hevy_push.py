"""Push data back to Hevy: planned workouts and body measurements.

Write-back is always human-triggered (CLI command); nothing here runs
automatically.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from ..api.client import HevyApiClient, HevyApiClientConflictError

PLANNED_WORKOUT_TYPE = "hevy-planned-workout"

MEASUREMENT_FIELDS = (
    "weight_kg",
    "fat_percent",
    "lean_mass_kg",
    "neck_cm",
    "shoulder_cm",
    "chest_cm",
    "left_bicep_cm",
    "right_bicep_cm",
    "left_forearm_cm",
    "right_forearm_cm",
    "abdomen",
    "waist",
    "hips",
    "left_thigh",
    "right_thigh",
    "left_calf",
    "right_calf",
)

_SET_TYPES = ("warmup", "normal", "failure", "dropset")


class PlannedWorkoutError(Exception):
    """Raised when a planned-workout note cannot be parsed."""


def _read_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        msg = f"{path.name}: no YAML frontmatter found."
        raise PlannedWorkoutError(msg)
    parts = text.split("---", 2)
    if len(parts) < 3:
        msg = f"{path.name}: unterminated YAML frontmatter."
        raise PlannedWorkoutError(msg)
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        msg = f"{path.name}: frontmatter is not a mapping."
        raise PlannedWorkoutError(msg)
    return data


def _coerce_iso(value: Any, fallback: datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).isoformat()
        except ValueError as err:
            msg = f"Invalid ISO 8601 timestamp: {value!r}"
            raise PlannedWorkoutError(msg) from err
    return fallback.isoformat()


def _parse_set(raw: Any, exercise_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        msg = f"{exercise_name}: each set must be a mapping, got {raw!r}"
        raise PlannedWorkoutError(msg)
    parsed: dict[str, Any] = {"type": raw.get("type", "normal")}
    if parsed["type"] not in _SET_TYPES:
        msg = f"{exercise_name}: invalid set type {parsed['type']!r}"
        raise PlannedWorkoutError(msg)
    for key, caster in (
        ("weight_kg", float),
        ("reps", int),
        ("distance_meters", int),
        ("duration_seconds", int),
        ("rpe", float),
        ("custom_metric", float),
    ):
        if raw.get(key) is not None:
            parsed[key] = caster(raw[key])
    return parsed


def parse_planned_workout(path: Path) -> dict[str, Any]:
    """Parse a planned-workout note into a POST /v1/workouts body."""
    data = _read_frontmatter(path)
    if data.get("type") != PLANNED_WORKOUT_TYPE:
        msg = (
            f"{path.name}: frontmatter 'type' must be "
            f"'{PLANNED_WORKOUT_TYPE}' (got {data.get('type')!r})."
        )
        raise PlannedWorkoutError(msg)

    title = data.get("title")
    if not title:
        msg = f"{path.name}: 'title' is required."
        raise PlannedWorkoutError(msg)

    raw_exercises = data.get("exercises")
    if not isinstance(raw_exercises, list) or not raw_exercises:
        msg = f"{path.name}: 'exercises' must be a non-empty list."
        raise PlannedWorkoutError(msg)

    exercises: list[dict[str, Any]] = []
    for raw in raw_exercises:
        name = raw.get("name") or raw.get("exercise_template_id") or "exercise"
        template_id = raw.get("exercise_template_id") or raw.get("template_id")
        if not template_id:
            msg = f"{path.name}: exercise {name!r} is missing exercise_template_id."
            raise PlannedWorkoutError(msg)
        sets = raw.get("sets")
        if not isinstance(sets, list) or not sets:
            msg = f"{path.name}: exercise {name!r} needs a non-empty 'sets' list."
            raise PlannedWorkoutError(msg)
        exercise: dict[str, Any] = {
            "exercise_template_id": str(template_id),
            "sets": [_parse_set(s, str(name)) for s in sets],
        }
        if raw.get("notes"):
            exercise["notes"] = str(raw["notes"])
        if raw.get("superset_id") is not None:
            exercise["superset_id"] = int(raw["superset_id"])
        exercises.append(exercise)

    now = datetime.now(tz=UTC)
    workout: dict[str, Any] = {
        "title": str(title),
        "start_time": _coerce_iso(data.get("start_time"), now - timedelta(hours=1)),
        "end_time": _coerce_iso(data.get("end_time"), now),
        "is_private": bool(data.get("is_private", False)),
        "exercises": exercises,
    }
    if data.get("description"):
        workout["description"] = str(data["description"])
    return {"workout": workout}


async def push_workout(client: HevyApiClient, body: dict[str, Any]) -> dict[str, Any]:
    """Create a workout in Hevy."""
    return await client.async_create_workout(body)


async def push_measurement(
    client: HevyApiClient,
    fields: dict[str, float],
    date_str: str | None = None,
) -> str:
    """Log a body measurement; on 409 (date exists) overwrite via PUT.

    Returns the date the measurement was written for.
    """
    if not fields:
        msg = "At least one measurement field is required."
        raise ValueError(msg)
    unknown = set(fields) - set(MEASUREMENT_FIELDS)
    if unknown:
        msg = f"Unknown measurement fields: {sorted(unknown)}"
        raise ValueError(msg)
    date_str = date_str or datetime.now(tz=UTC).date().isoformat()
    body = {**fields, "date": date_str}
    try:
        await client.async_create_body_measurement(body)
    except HevyApiClientConflictError:
        await client.async_update_body_measurement(date_str, dict(fields))
    return date_str
