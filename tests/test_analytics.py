"""Tests for stats, PRs, and pattern analysis."""

from __future__ import annotations

from datetime import date

from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics import patterns, stats
from hevy_brain.analytics.prs import (
    epley_1rm,
    exercise_histories,
    prs_for_workout,
    recent_prs,
)
from hevy_brain.models import build_records

TODAY = date(2026, 6, 10)


def test_build_records_sorted_and_volumes(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)

    assert [r["id"] for r in records] == ["w1", "w2", "w3"]
    w1 = records[0]
    # 60*8 + 60*8 + 10*12 = 1080
    assert w1["volume_kg"] == 1080
    assert w1["total_reps"] == 28
    assert w1["duration_seconds"] == 3600


def test_aggregates_and_streaks(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    agg = stats.compute_aggregates(records, TODAY)

    assert agg["total_workouts"] == 3
    assert agg["week_count"] == 1  # only w3 within 7 days of 2026-06-10
    assert agg["month_count"] == 2  # w2 + w3 in June
    assert agg["year_count"] == 3
    assert agg["current_streak_days"] == 0


def test_streaks_current_and_longest() -> None:
    dates = {
        date(2026, 6, 10),
        date(2026, 6, 9),
        date(2026, 6, 5),
        date(2026, 6, 4),
        date(2026, 6, 3),
    }
    current, longest = stats.compute_streaks(dates, date(2026, 6, 10))
    assert current == 2
    assert longest == 3


def test_epley() -> None:
    assert epley_1rm(100, 1) == 100
    assert epley_1rm(100, 10) == 100 * (1 + 10 / 30)
    assert epley_1rm(0, 5) == 0
    assert epley_1rm(100, 0) == 0


def test_exercise_histories_and_prs(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)

    bench = histories["Bench Press (Barbell)"]
    assert bench["times_performed"] == 2
    assert bench["best_weight_kg"] == 70
    # First session sets baselines without PRs; w3 beats weight + e1rm.
    pr_types = {pr["type"] for pr in bench["prs"]}
    assert "weight" in pr_types
    assert all(pr["workout_id"] == "w3" for pr in bench["prs"])

    w3_prs = prs_for_workout(histories, "w3")
    assert any(p["exercise"] == "Bench Press (Barbell)" for p in w3_prs)
    assert prs_for_workout(histories, "w1") == []

    assert recent_prs(histories)[0]["date"] == date(2026, 6, 8)


def test_muscle_grouping_template_overrides_and_keywords() -> None:
    templates = {"T-X": {"title": "Mystery Move", "primary_muscle_group": "lats"}}
    assert patterns.muscle_group("Mystery Move", "T-X", templates) == "back"
    assert patterns.muscle_group("Bench Press (Barbell)") == "chest"
    assert patterns.muscle_group("Lat Pulldown (Cable)") == "back"
    assert patterns.muscle_group("Bizarre Movement") == "other"
    assert (
        patterns.muscle_group("Bizarre Movement", overrides={"bizarre": "core"})
        == "core"
    )


def test_volume_by_group_and_push_pull(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    volumes = patterns.volume_by_group(records)

    assert volumes["chest"] == 60 * 8 * 2 + 65 * 8 + 70 * 5
    assert volumes["back"] == 70 * 10 + 55 * 10
    ratio = patterns.push_pull_ratio(volumes)
    assert ratio is not None
    assert ratio > 1


def test_volume_by_group_breaks_exact_ties_by_name() -> None:
    # chest (bench) and back (row) both 50*8 = 400 kg -> ascending name on the tie
    records = build_records(
        {
            "a": make_workout(
                "a",
                exercises=[
                    make_exercise("Bench Press (Barbell)", "T-B", [make_set(50, 8)]),
                    make_exercise(
                        "Bent Over Row (Barbell)", "T-ROW", [make_set(50, 8)], 1
                    ),
                ],
            )
        }
    )
    volumes = patterns.volume_by_group(records)
    assert list(volumes)[:2] == ["back", "chest"]


def test_plateau_detection() -> None:
    # 4 recent sessions stuck at 100kg e1rm; prior window reached the same.
    workouts = {}
    for i, day in enumerate(("2026-05-18", "2026-05-25", "2026-06-01", "2026-06-08")):
        workouts[f"r{i}"] = make_workout(
            f"r{i}",
            "Push",
            start=f"{day}T17:00:00+00:00",
            end=f"{day}T18:00:00+00:00",
            exercises=[make_exercise(sets=[make_set(100, 1)])],
        )
    for i, day in enumerate(("2026-04-20", "2026-04-27", "2026-05-04")):
        workouts[f"p{i}"] = make_workout(
            f"p{i}",
            "Push",
            start=f"{day}T17:00:00+00:00",
            end=f"{day}T18:00:00+00:00",
            exercises=[make_exercise(sets=[make_set(100, 1)])],
        )
    histories = exercise_histories(build_records(workouts))
    plateaus = patterns.detect_plateaus(histories, date(2026, 6, 10), plateau_weeks=4)

    assert len(plateaus) == 1
    assert plateaus[0]["exercise"] == "Bench Press (Barbell)"


def test_no_plateau_when_progressing() -> None:
    workouts = {}
    weights = (100, 102.5, 105, 107.5)
    for i, (day, weight) in enumerate(
        zip(
            ("2026-05-18", "2026-05-25", "2026-06-01", "2026-06-08"),
            weights,
            strict=True,
        )
    ):
        workouts[f"r{i}"] = make_workout(
            f"r{i}",
            "Push",
            start=f"{day}T17:00:00+00:00",
            end=f"{day}T18:00:00+00:00",
            exercises=[make_exercise(sets=[make_set(weight, 1)])],
        )
    workouts["p0"] = make_workout(
        "p0",
        "Push",
        start="2026-04-27T17:00:00+00:00",
        end="2026-04-27T18:00:00+00:00",
        exercises=[make_exercise(sets=[make_set(100, 1)])],
    )
    histories = exercise_histories(build_records(workouts))
    assert patterns.detect_plateaus(histories, date(2026, 6, 10)) == []


def test_weekly_overload(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    deltas = patterns.weekly_overload(records, TODAY)

    bench = next(d for d in deltas if d["exercise"] == "Bench Press (Barbell)")
    assert bench["last_week_kg"] == 65 * 8 + 70 * 5
    assert bench["prior_week_kg"] == 0


def test_warmup_sets_excluded_from_best_e1rm() -> None:
    # A (mislabelled) heavier warm-up must NOT set the session's e1RM or best
    # set — the working set does. best_weight_kg still counts every set, mirroring
    # max_weight_kg / volume_kg.
    records = build_records(
        {
            "w1": make_workout(
                "w1",
                exercises=[
                    make_exercise(
                        sets=[make_set(200, 5, type="warmup"), make_set(100, 5)]
                    )
                ],
            )
        }
    )
    bench = exercise_histories(records)["Bench Press (Barbell)"]
    session = bench["sessions"][0]
    assert session["best_set"]["weight_kg"] == 100  # the working set, not 200
    assert round(session["best_e1rm_kg"], 2) == round(epley_1rm(100, 5), 2)
    assert bench["best_weight_kg"] == 200  # warm-up still counts toward weight


def test_all_warmup_history_yields_no_e1rm_and_no_plateau() -> None:
    # Seven warm-up-only sessions (enough to fill the plateau windows) must read
    # as 0 e1RM with no best set, so detect_plateaus does NOT fire — the
    # warm-up-set bug regression (without the fix, every session's e1RM would be
    # the warm-up's and a flat run would falsely plateau).
    days = (
        "2026-04-20",
        "2026-04-27",
        "2026-05-04",
        "2026-05-18",
        "2026-05-25",
        "2026-06-01",
        "2026-06-08",
    )
    workouts = {
        f"d{i}": make_workout(
            f"d{i}",
            "Push",
            start=f"{day}T17:00:00+00:00",
            end=f"{day}T18:00:00+00:00",
            exercises=[make_exercise(sets=[make_set(50, 5, type="warmup")])],
        )
        for i, day in enumerate(days)
    }
    histories = exercise_histories(build_records(workouts))
    bench = histories["Bench Press (Barbell)"]
    assert all(s["best_e1rm_kg"] == 0.0 for s in bench["sessions"])
    assert all(s["best_set"] is None for s in bench["sessions"])
    assert bench["best_e1rm_kg"] == 0.0
    assert (
        patterns.detect_plateaus(histories, date(2026, 6, 10), plateau_weeks=4) == []
    )
