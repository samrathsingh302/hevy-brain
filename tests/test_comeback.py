"""Tests for lapse detection and pre-lapse baselines (guide return, E1)."""

from __future__ import annotations

from datetime import date

import pytest

from hevy_brain.analytics.comeback import lapse_status, pre_lapse_baselines
from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.models import build_records

# Fixture workouts land on 2026-05-25, 2026-06-01 and 2026-06-08.
LAPSED_TODAY = date(2026, 8, 10)


def test_lapse_status_counts_days_since_last_workout(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)

    status = lapse_status(records, LAPSED_TODAY)

    assert status is not None
    assert status["last_workout_date"] == date(2026, 6, 8)
    assert status["last_workout_title"] == "Push Day"
    assert status["days_since"] == 63


def test_lapse_status_empty_history() -> None:
    assert lapse_status([], LAPSED_TODAY) is None


def test_lapse_status_recent_training_is_small_gap(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)

    status = lapse_status(records, date(2026, 6, 10))

    assert status is not None
    assert status["days_since"] == 2


def test_pre_lapse_baselines_window_and_volume(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)

    base = pre_lapse_baselines(records, histories, weeks=4)

    # Window ends at the LAST workout, not today — the lapse never dilutes it.
    assert base["window_end"] == date(2026, 6, 8)
    assert base["window_start"] == date(2026, 5, 12)
    assert base["sessions"] == 3
    assert base["sessions_per_week"] == pytest.approx(0.75)
    # w1: 960 + 120, w2: 700 + 550, w3: 520 + 350.
    assert base["volume_kg"] == pytest.approx(3200.0)
    assert base["weekly_volume_kg"] == pytest.approx(800.0)
    assert base["workout_titles"] == ["Pull Day", "Push Day"]


def test_pre_lapse_baselines_narrow_window_excludes_older(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)

    base = pre_lapse_baselines(records, histories, weeks=1)

    # Only the 2026-06-08 session falls in the final 7 days.
    assert base["sessions"] == 1
    assert base["volume_kg"] == pytest.approx(870.0)


def test_pre_lapse_baselines_top_exercises(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)

    base = pre_lapse_baselines(records, histories, weeks=4)

    top = base["top_exercises"]
    assert top[0]["title"] == "Bench Press (Barbell)"
    assert top[0]["sessions"] == 2
    assert top[0]["volume_kg"] == pytest.approx(1830.0)
    assert top[0]["top_weight_kg"] == pytest.approx(70.0)
    # Best window e1RM: 65 kg x 8 reps -> 65 * (1 + 8/30).
    assert top[0]["window_e1rm_kg"] == pytest.approx(65 * (1 + 8 / 30))
    assert top[0]["all_time_e1rm_kg"] == pytest.approx(65 * (1 + 8 / 30))


def test_pre_lapse_baselines_muscle_groups(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)

    base = pre_lapse_baselines(records, histories, weeks=4)

    assert base["volume_by_group"]["chest"] == pytest.approx(1830.0)
    assert base["volume_by_group"]["back"] == pytest.approx(1250.0)
