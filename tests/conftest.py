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
