"""Push data back to Hevy: planned workouts and body measurements.

Write-back is always human-triggered (CLI command); nothing here runs
automatically.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from ..api.client import HevyApiClient, HevyApiClientConflictError
from ..clock import today_london
from ..models import build_workout_record, parse_iso
from ..vault.routines import ROUTINE_NOTE_TYPE, routine_exercises_spec
from ..vault.workouts import WORKOUT_NOTE_TYPE, workout_exercises_spec

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

# Hevy workout sets accept RPE 6-10 in half-point steps (routine sets do not).
_VALID_RPE = frozenset({6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0})


class PlannedWorkoutError(Exception):
    """Raised when a planned-workout note cannot be parsed."""


class WorkoutNoteError(Exception):
    """Raised when a logged-workout note cannot be parsed for an update."""


class RoutineNoteError(Exception):
    """Raised when a routine note cannot be parsed."""


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


def _parse_workout_set(raw: Any, exercise_name: str) -> dict[str, Any]:
    """Parse one workout set. Workout sets accept RPE (6-10 in halves)."""
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
    if parsed.get("rpe") is not None and parsed["rpe"] not in _VALID_RPE:
        msg = (
            f"{exercise_name}: RPE must be 6–10 in half-point steps, "
            f"got {parsed['rpe']:g}."
        )
        raise PlannedWorkoutError(msg)
    return parsed


def _parse_workout_exercises(raw_exercises: Any, path: Path) -> list[dict[str, Any]]:
    """Parse the 'exercises' list shared by create and update workout bodies."""
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
            "sets": [_parse_workout_set(s, str(name)) for s in sets],
        }
        if raw.get("notes"):
            exercise["notes"] = str(raw["notes"])
        if raw.get("superset_id") is not None:
            exercise["superset_id"] = int(raw["superset_id"])
        exercises.append(exercise)
    return exercises


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

    exercises = _parse_workout_exercises(data.get("exercises"), path)

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


def parse_workout_note(path: Path) -> tuple[str, dict[str, Any]]:
    """Parse a logged-workout note into (workout_id, PUT /v1/workouts/{id} body).

    Accepts any note whose frontmatter has ``type: hevy-workout`` — the
    managed note or (safer, since managed notes regenerate on sync) a draft
    copy of it. PUT is a FULL replacement: the body is built entirely from
    the note, so start_time/end_time are required (a missing time must never
    silently reset the logged session to "now").
    """
    try:
        data = _read_frontmatter(path)
    except PlannedWorkoutError as err:
        raise WorkoutNoteError(str(err)) from err

    if data.get("type") != WORKOUT_NOTE_TYPE:
        msg = (
            f"{path.name}: frontmatter 'type' must be "
            f"'{WORKOUT_NOTE_TYPE}' (got {data.get('type')!r})."
        )
        raise WorkoutNoteError(msg)

    workout_id = data.get("hevy_id")
    if not workout_id:
        msg = f"{path.name}: 'hevy_id' is required."
        raise WorkoutNoteError(msg)

    title = data.get("title")
    if not title:
        msg = f"{path.name}: 'title' is required."
        raise WorkoutNoteError(msg)

    if data.get("start_time") is None or data.get("end_time") is None:
        msg = f"{path.name}: 'start_time' and 'end_time' are required for an update."
        raise WorkoutNoteError(msg)

    try:
        exercises = _parse_workout_exercises(data.get("exercises"), path)
        now = datetime.now(tz=UTC)
        workout: dict[str, Any] = {
            "title": str(title),
            "start_time": _coerce_iso(data.get("start_time"), now),
            "end_time": _coerce_iso(data.get("end_time"), now),
            "is_private": bool(data.get("is_private", False)),
            "exercises": exercises,
        }
    except PlannedWorkoutError as err:
        raise WorkoutNoteError(str(err)) from err
    if data.get("description"):
        workout["description"] = str(data["description"])
    return str(workout_id), {"workout": workout}


async def push_workout(client: HevyApiClient, body: dict[str, Any]) -> dict[str, Any]:
    """Create a workout in Hevy."""
    return await client.async_create_workout(body)


def _parse_routine_set(raw: Any, exercise_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        msg = f"{exercise_name}: each set must be a mapping, got {raw!r}"
        raise RoutineNoteError(msg)
    if raw.get("rpe") is not None:
        msg = f"{exercise_name}: routine sets do not support RPE (workout sets do)."
        raise RoutineNoteError(msg)
    parsed: dict[str, Any] = {"type": raw.get("type", "normal")}
    if parsed["type"] not in _SET_TYPES:
        msg = f"{exercise_name}: invalid set type {parsed['type']!r}"
        raise RoutineNoteError(msg)
    for key, caster in (
        ("weight_kg", float),
        ("reps", int),
        ("distance_meters", int),
        ("duration_seconds", int),
        ("custom_metric", float),
    ):
        if raw.get(key) is not None:
            parsed[key] = caster(raw[key])
    rep_range = raw.get("rep_range")
    if rep_range is not None:
        if not isinstance(rep_range, dict) or rep_range.get("start") is None:
            msg = f"{exercise_name}: rep_range needs at least 'start'."
            raise RoutineNoteError(msg)
        # A null 'end' is a real Hevy state ("8+ reps") — the live account
        # has one. Full-replacement fidelity: keep it exactly as the API
        # returned it instead of rejecting or inventing an end.
        end = rep_range.get("end")
        parsed["rep_range"] = {
            "start": int(rep_range["start"]),
            "end": int(end) if end is not None else None,
        }
    return parsed


def parse_routine_note(path: Path) -> tuple[str, dict[str, Any]]:
    """Parse a routine note into (routine_id, PUT /v1/routines/{id} body).

    Accepts any note whose frontmatter has ``type: hevy-routine`` — the
    managed note or (safer, since managed notes regenerate on sync) a draft
    copy of it. PUT is a FULL replacement: the body is built entirely from
    the note; anything missing from it is removed from the routine in Hevy.
    """
    try:
        data = _read_frontmatter(path)
    except PlannedWorkoutError as err:
        raise RoutineNoteError(str(err)) from err

    if data.get("type") != ROUTINE_NOTE_TYPE:
        msg = (
            f"{path.name}: frontmatter 'type' must be "
            f"'{ROUTINE_NOTE_TYPE}' (got {data.get('type')!r})."
        )
        raise RoutineNoteError(msg)

    routine_id = data.get("hevy_routine_id")
    if not routine_id:
        msg = f"{path.name}: 'hevy_routine_id' is required."
        raise RoutineNoteError(msg)

    title = data.get("title")
    if not title:
        msg = f"{path.name}: 'title' is required."
        raise RoutineNoteError(msg)

    raw_exercises = data.get("exercises")
    if not isinstance(raw_exercises, list) or not raw_exercises:
        msg = f"{path.name}: 'exercises' must be a non-empty list."
        raise RoutineNoteError(msg)

    exercises: list[dict[str, Any]] = []
    for raw in raw_exercises:
        name = raw.get("name") or raw.get("exercise_template_id") or "exercise"
        template_id = raw.get("exercise_template_id")
        if not template_id:
            msg = f"{path.name}: exercise {name!r} is missing exercise_template_id."
            raise RoutineNoteError(msg)
        sets = raw.get("sets")
        if not isinstance(sets, list) or not sets:
            msg = f"{path.name}: exercise {name!r} needs a non-empty 'sets' list."
            raise RoutineNoteError(msg)
        exercise: dict[str, Any] = {
            "exercise_template_id": str(template_id),
            "sets": [_parse_routine_set(s, str(name)) for s in sets],
        }
        if raw.get("superset_id") is not None:
            exercise["superset_id"] = int(raw["superset_id"])
        if raw.get("rest_seconds") is not None:
            exercise["rest_seconds"] = int(raw["rest_seconds"])
        if raw.get("notes"):
            exercise["notes"] = str(raw["notes"])
        exercises.append(exercise)

    routine: dict[str, Any] = {"title": str(title)}
    # Hevy rejects "notes": "" with a 400 and treats a missing key as "clear
    # the notes" (PUT is a full replacement) — verified live 13/06/2026. So:
    # notes in the frontmatter are sent; no notes line means none in Hevy.
    notes = str(data.get("notes") or "")
    if notes:
        routine["notes"] = notes
    routine["exercises"] = exercises
    return str(routine_id), {"routine": routine}


def _set_summary(routine_set: dict[str, Any]) -> str:
    parts = [routine_set.get("type", "normal")]
    if routine_set.get("weight_kg") is not None:
        parts.append(f"{routine_set['weight_kg']:g}kg")
    if routine_set.get("reps") is not None:
        parts.append(f"×{routine_set['reps']}")
    elif routine_set.get("rep_range"):
        rng = routine_set["rep_range"]
        end = rng.get("end")
        suffix = f"–{end}" if end is not None else "+"
        parts.append(f"×{rng.get('start')}{suffix}")
    if routine_set.get("duration_seconds"):
        parts.append(f"{routine_set['duration_seconds']}s")
    if routine_set.get("distance_meters"):
        parts.append(f"{routine_set['distance_meters']}m")
    return " ".join(str(p) for p in parts)


def _workout_set_summary(workout_set: dict[str, Any]) -> str:
    parts = [workout_set.get("type", "normal")]
    if workout_set.get("weight_kg") is not None:
        parts.append(f"{workout_set['weight_kg']:g}kg")
    if workout_set.get("reps") is not None:
        parts.append(f"×{workout_set['reps']}")
    if workout_set.get("duration_seconds"):
        parts.append(f"{workout_set['duration_seconds']}s")
    if workout_set.get("distance_meters"):
        parts.append(f"{workout_set['distance_meters']}m")
    if workout_set.get("rpe") is not None:
        parts.append(f"RPE {workout_set['rpe']:g}")
    return " ".join(str(p) for p in parts)


def _comparable_exercise(spec: dict[str, Any]) -> dict[str, Any]:
    """Strip display-only keys so server and note specs compare equal."""
    return {k: v for k, v in spec.items() if k != "name"}


def _exercise_diff(
    cur_exercises: list[dict[str, Any]],
    new_exercises: list[dict[str, Any]],
    *,
    set_summary: Callable[[dict[str, Any]], str],
    exercise_keys: tuple[str, ...],
) -> list[str]:
    """Diff two normalised exercise-spec lists (shared by routines + workouts).

    Callers supply the per-set renderer and which per-exercise keys to compare;
    top-level fields (title/notes/times) are diffed by the caller. Empty list
    for identical lists, so an unedited note round-trips clean.
    """
    lines: list[str] = []
    for index in range(max(len(cur_exercises), len(new_exercises))):
        if index >= len(cur_exercises):
            added = new_exercises[index]
            label = added.get("name") or added["exercise_template_id"]
            lines.append(f"+ exercise {index + 1}: {label} ({len(added['sets'])} sets)")
            continue
        if index >= len(new_exercises):
            removed = cur_exercises[index]
            lines.append(f"− exercise {index + 1}: {removed['name']}")
            continue

        cur = cur_exercises[index]
        new_ex = new_exercises[index]
        label = cur.get("name") or cur["exercise_template_id"]
        if cur["exercise_template_id"] != new_ex["exercise_template_id"]:
            lines.append(
                f"~ exercise {index + 1}: {cur['exercise_template_id']} → "
                f"{new_ex['exercise_template_id']}"
            )
            continue
        if _comparable_exercise(cur) == _comparable_exercise(new_ex):
            continue
        cur_sets = cur.get("sets", [])
        new_sets = new_ex.get("sets", [])
        if len(cur_sets) != len(new_sets):
            lines.append(f"~ {label}: sets {len(cur_sets)} → {len(new_sets)}")
        for set_index, (a, b) in enumerate(
            zip(cur_sets, new_sets, strict=False), start=1
        ):
            if a != b:
                lines.append(
                    f"~ {label}: set {set_index}: {set_summary(a)} → {set_summary(b)}"
                )
        for key in exercise_keys:
            if cur.get(key) != new_ex.get(key):
                lines.append(
                    f"~ {label}: {key}: {cur.get(key)!r} → {new_ex.get(key)!r}"
                )
    return lines


def routine_diff(current: dict[str, Any], body: dict[str, Any]) -> list[str]:
    """Human-readable diff between the routine in Hevy and the note's body.

    Empty list = no changes. Compared on the same normalised spec the vault
    notes are generated from, so an unedited note diffs clean.
    """
    lines: list[str] = []
    new = body["routine"]
    if (current.get("title") or "") != new["title"]:
        lines.append(f"~ title: {current.get('title')!r} → {new['title']!r}")
    if (current.get("notes") or "") != (new.get("notes") or ""):
        lines.append("~ routine notes changed")
    lines += _exercise_diff(
        routine_exercises_spec(current),
        new["exercises"],
        set_summary=_set_summary,
        exercise_keys=("rest_seconds", "superset_id", "notes"),
    )
    return lines


def _to_utc(value: Any) -> datetime | None:
    """Normalise an ISO string or datetime to a UTC-aware datetime.

    PyYAML loads an unquoted timestamp as a (UTC-converted) datetime and a
    quoted one as a string; the parser emits ISO strings. Normalising both
    sides means an unedited time never shows as a spurious diff.
    """
    dt = parse_iso(value) if isinstance(value, str) else value
    if not isinstance(dt, datetime):
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def workout_diff(current: dict[str, Any], body: dict[str, Any]) -> list[str]:
    """Human-readable diff between the workout in Hevy and the note's body.

    Empty list = no changes. The server payload is normalised through the same
    record→spec path the vault notes are built from, so an unedited note diffs
    clean.
    """
    lines: list[str] = []
    new = body["workout"]
    if (current.get("title") or "") != new["title"]:
        lines.append(f"~ title: {current.get('title')!r} → {new['title']!r}")
    if (current.get("description") or "") != (new.get("description") or ""):
        lines.append("~ workout description changed")
    cur_private = bool(current.get("is_private", False))
    new_private = bool(new.get("is_private", False))
    if cur_private != new_private:
        lines.append(f"~ is_private: {cur_private} → {new_private}")
    for field in ("start_time", "end_time"):
        if _to_utc(current.get(field)) != _to_utc(new.get(field)):
            lines.append(f"~ {field}: {current.get(field)} → {new.get(field)}")

    record = build_workout_record(current)
    lines += _exercise_diff(
        workout_exercises_spec(record),
        new["exercises"],
        set_summary=_workout_set_summary,
        exercise_keys=("superset_id", "notes"),
    )
    return lines


def unwrap_routine(payload: Any) -> dict[str, Any] | None:
    """Pull the routine object out of a GET /v1/routines/{id} response."""
    return _unwrap(payload, "routine")


def unwrap_workout(payload: Any) -> dict[str, Any] | None:
    """Pull the workout object out of a GET /v1/workouts/{id} response."""
    return _unwrap(payload, "workout")


def _unwrap(payload: Any, key: str) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        inner = payload.get(key, payload)
        if isinstance(inner, list):
            inner = inner[0] if inner else None
        return inner if isinstance(inner, dict) else None
    return None


async def push_routine(
    client: HevyApiClient, routine_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    """PUT (full replacement) a routine in Hevy."""
    return await client.async_update_routine(routine_id, body)


async def push_workout_update(
    client: HevyApiClient, workout_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    """PUT (full replacement) a logged workout in Hevy."""
    return await client.async_update_workout(workout_id, body)


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
    date_str = date_str or today_london().isoformat()
    body = {**fields, "date": date_str}
    try:
        await client.async_create_body_measurement(body)
    except HevyApiClientConflictError:
        await client.async_update_body_measurement(date_str, dict(fields))
    return date_str
