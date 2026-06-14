"""Tests for coach memory: focus snapshots + the honest adherence recap."""

from __future__ import annotations

from datetime import date

from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.coach import memory
from hevy_brain.models import build_records

TODAY = date(2026, 6, 13)


def _bench_records() -> tuple[list, dict]:
    """Bench on 2026-05-01 (lighter) then 2026-06-08 (heavier)."""
    raw = {
        "a": make_workout(
            "a",
            start="2026-05-01T17:00:00+00:00",
            end="2026-05-01T18:00:00+00:00",
            exercises=[
                make_exercise("Bench Press (Barbell)", "T-B", [make_set(60, 8)])
            ],
        ),
        "b": make_workout(
            "b",
            start="2026-06-08T17:00:00+00:00",
            end="2026-06-08T18:00:00+00:00",
            exercises=[
                make_exercise("Bench Press (Barbell)", "T-B", [make_set(70, 5)])
            ],
        ),
    }
    records = build_records(raw)
    return records, exercise_histories(records)


# --- snapshot persistence ----------------------------------------------------


def test_build_focus_snapshot_fields() -> None:
    records, histories = _bench_records()
    snap = memory.build_focus_snapshot(
        records, histories, TODAY, path="free", plateau_weeks=4
    )
    assert snap["taken_on"] == "2026-06-13"
    assert snap["path"] == "free"
    assert "push_pull_ratio" in snap
    assert snap["plateau_weeks"] == 4
    assert isinstance(snap["plateaus"], list)
    assert isinstance(snap["sessions_last_7d"], int)


def test_record_and_latest_focus_bounded() -> None:
    meta: dict = {}
    assert memory.latest_focus(meta) is None

    for i in range(15):
        memory.record_focus(meta, {"taken_on": f"2026-06-{i + 1:02d}", "path": "free"})

    assert len(meta[memory.META_KEY]) == 12  # capped
    assert memory.latest_focus(meta)["taken_on"] == "2026-06-15"


# --- adherence recap ---------------------------------------------------------


def test_grade_focus_none_without_prior() -> None:
    records, histories = _bench_records()
    assert memory.grade_focus(None, records, histories, TODAY, plateau_weeks=4) is None
    assert (
        memory.grade_focus({"plateaus": []}, records, histories, TODAY, plateau_weeks=4)
        is None
    )  # no taken_on


def test_grade_focus_nothing_to_grade_when_no_new_sessions() -> None:
    records, histories = _bench_records()
    prev = {"taken_on": "2026-06-09", "plateaus": []}  # after both workouts
    recap = memory.grade_focus(prev, records, histories, TODAY, plateau_weeks=4)
    assert recap is not None
    assert "nothing to grade yet" in recap
    assert "Sessions logged since" not in recap


def test_grade_focus_plateau_improved() -> None:
    records, histories = _bench_records()
    prev = {
        "taken_on": "2026-05-15",
        "sessions_last_7d": 0,
        "push_pull_ratio": None,
        "plateaus": [{"exercise": "Bench Press (Barbell)", "e1rm_kg": 76.0}],
    }
    recap = memory.grade_focus(prev, records, histories, TODAY, plateau_weeks=4)
    # new session 2026-06-08: e1RM epley(70,5)=81.7 > 76 + tolerance
    assert "Bench Press (Barbell)" in recap
    assert "improved" in recap
    assert "Sessions logged since: **1**" in recap


def test_grade_focus_plateau_regressed_and_cant_grade() -> None:
    records, histories = _bench_records()
    prev = {
        "taken_on": "2026-05-15",
        "plateaus": [
            {"exercise": "Bench Press (Barbell)", "e1rm_kg": 95.0},  # nothing beats it
            {"exercise": "Deadlift (Barbell)", "e1rm_kg": 180.0},  # never trained
        ],
    }
    recap = memory.grade_focus(prev, records, histories, TODAY, plateau_weeks=4)
    assert "regressed" in recap
    assert "can't grade" in recap


def test_grade_focus_plateau_held_within_tolerance() -> None:
    records, histories = _bench_records()
    # new best e1RM = epley(70,5) = 81.7; a prior within +/-0.5 kg -> held
    prev = {
        "taken_on": "2026-05-15",
        "plateaus": [{"exercise": "Bench Press (Barbell)", "e1rm_kg": 81.5}],
    }
    recap = memory.grade_focus(prev, records, histories, TODAY, plateau_weeks=4)
    assert "**held**" in recap


def test_grade_focus_consistency_trend_words() -> None:
    records, histories = _bench_records()  # week_count at TODAY = 1 (the 06-08 session)
    up = memory.grade_focus(
        {"taken_on": "2026-05-15", "sessions_last_7d": 0, "plateaus": []},
        records,
        histories,
        TODAY,
        plateau_weeks=4,
    )
    assert "Consistency: 0 → 1 sessions in the last 7 days — **up**" in up

    flat = memory.grade_focus(
        {"taken_on": "2026-05-15", "sessions_last_7d": 1, "plateaus": []},
        records,
        histories,
        TODAY,
        plateau_weeks=4,
    )
    assert "— **flat**" in flat


def test_grade_focus_pushpull_line_renders_with_pull_volume() -> None:
    raw = {
        "a": make_workout(
            "a",
            start="2026-06-08T17:00:00+00:00",
            end="2026-06-08T18:00:00+00:00",
            exercises=[
                make_exercise("Bench Press (Barbell)", "T-B", [make_set(60, 8)]),
                make_exercise("Bent Over Row (Barbell)", "T-ROW", [make_set(50, 8)], 1),
            ],
        )
    }
    records = build_records(raw)
    histories = exercise_histories(records)
    prev = {"taken_on": "2026-06-01", "push_pull_ratio": 1.60, "plateaus": []}
    recap = memory.grade_focus(prev, records, histories, TODAY, plateau_weeks=4)
    # push 480 / pull 400 = 1.20; moved toward 1.0 from 1.60
    assert "Push/pull balance: 1.60 → 1.20" in recap
    assert "rebalancing toward 1.0" in recap


def test_grade_focus_bench_only_skips_pushpull_line() -> None:
    records, histories = _bench_records()
    prev = {"taken_on": "2026-05-15", "push_pull_ratio": 1.60, "plateaus": []}
    recap = memory.grade_focus(prev, records, histories, TODAY, plateau_weeks=4)
    # bench-only data has no pull volume -> current ratio is None -> line skipped
    assert "Push/pull balance" not in recap


def test_grade_focus_tolerates_malformed_snapshot() -> None:
    """A hand-edited/old-schema meta.json must never crash the coach run."""
    records, histories = _bench_records()
    prev = {
        "taken_on": "2026-05-15",
        "sessions_last_7d": "lots",  # wrong type — line skipped, no crash
        "push_pull_ratio": "n/a",  # wrong type — line skipped, no crash
        "plateaus": [
            {"e1rm_kg": 50.0},  # missing 'exercise' — item skipped
            "not-a-dict",  # not a mapping — item skipped
            {"exercise": "Bench Press (Barbell)", "e1rm_kg": 76.0},  # valid
        ],
    }
    recap = memory.grade_focus(prev, records, histories, TODAY, plateau_weeks=4)
    assert recap is not None  # did not crash
    assert "Bench Press (Barbell)" in recap  # the one valid plateau still graded


def test_grade_focus_bad_taken_on_type_returns_none() -> None:
    records, histories = _bench_records()
    assert (
        memory.grade_focus(
            {"taken_on": 12345}, records, histories, TODAY, plateau_weeks=4
        )
        is None
    )
