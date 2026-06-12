"""Shared fixtures: factories for raw Hevy API payloads."""

from __future__ import annotations

from typing import Any

import pytest


def make_set(weight_kg: float | None = 60, reps: int | None = 8, **extra: Any) -> dict:
    """Build a raw API set payload."""
    return {"type": "normal", "weight_kg": weight_kg, "reps": reps, **extra}


def make_exercise(
    title: str = "Bench Press (Barbell)",
    template_id: str = "T-BENCH",
    sets: list[dict] | None = None,
    index: int = 0,
) -> dict:
    """Build a raw API exercise payload."""
    return {
        "index": index,
        "title": title,
        "exercise_template_id": template_id,
        "notes": None,
        "sets": sets if sets is not None else [make_set(), make_set()],
    }


def make_workout(
    workout_id: str = "w1",
    title: str = "Push Day",
    start: str = "2026-06-08T17:00:00+00:00",
    end: str = "2026-06-08T18:00:00+00:00",
    exercises: list[dict] | None = None,
) -> dict:
    """Build a raw API workout payload."""
    return {
        "id": workout_id,
        "title": title,
        "description": None,
        "start_time": start,
        "end_time": end,
        "updated_at": end,
        "created_at": end,
        "exercises": exercises if exercises is not None else [make_exercise()],
    }


def make_routine_set(
    weight_kg: float | None = 60,
    reps: int | None = 8,
    **extra: Any,
) -> dict:
    """Build a raw API routine set payload (planned set — no RPE)."""
    return {
        "index": 0,
        "type": "normal",
        "weight_kg": weight_kg,
        "reps": reps,
        "distance_meters": None,
        "duration_seconds": None,
        "custom_metric": None,
        **extra,
    }


def make_routine_exercise(
    title: str = "Bench Press (Barbell)",
    template_id: str = "T-BENCH",
    sets: list[dict] | None = None,
    index: int = 0,
    rest_seconds: int | None = 120,
) -> dict:
    """Build a raw API routine exercise payload."""
    return {
        "index": index,
        "title": title,
        "exercise_template_id": template_id,
        "superset_id": None,
        "rest_seconds": rest_seconds,
        "notes": None,
        "sets": sets if sets is not None else [make_routine_set(), make_routine_set()],
    }


def make_routine(
    routine_id: str = "r1",
    title: str = "Push Day A",
    folder_id: int | None = None,
    exercises: list[dict] | None = None,
    updated_at: str = "2026-06-10T09:00:00+00:00",
) -> dict:
    """Build a raw API routine payload."""
    return {
        "id": routine_id,
        "title": title,
        "folder_id": folder_id,
        "notes": "",
        "created_at": "2026-05-01T09:00:00+00:00",
        "updated_at": updated_at,
        "exercises": exercises if exercises is not None else [make_routine_exercise()],
    }


@pytest.fixture
def raw_workouts() -> dict[str, dict]:
    """Three workouts across two weeks with progressing bench press."""
    w1 = make_workout(
        "w1",
        "Push Day",
        start="2026-05-25T17:00:00+00:00",
        end="2026-05-25T18:00:00+00:00",
        exercises=[
            make_exercise(sets=[make_set(60, 8), make_set(60, 8)]),
            make_exercise("Lateral Raise (Dumbbell)", "T-LAT", [make_set(10, 12)], 1),
        ],
    )
    w2 = make_workout(
        "w2",
        "Pull Day",
        start="2026-06-01T17:00:00+00:00",
        end="2026-06-01T18:10:00+00:00",
        exercises=[
            make_exercise("Bent Over Row (Barbell)", "T-ROW", [make_set(70, 10)]),
            make_exercise("Lat Pulldown (Cable)", "T-PULL", [make_set(55, 10)], 1),
        ],
    )
    w3 = make_workout(
        "w3",
        "Push Day",
        start="2026-06-08T17:00:00+00:00",
        end="2026-06-08T18:00:00+00:00",
        exercises=[
            make_exercise(sets=[make_set(65, 8), make_set(70, 5)]),
        ],
    )
    return {w["id"]: w for w in (w1, w2, w3)}
