"""Tests for the per-year Year-in-Review notes."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.models import build_records
from hevy_brain.vault.writer import VaultWriter
from hevy_brain.vault.yearreview import generate_year_reviews, render_year_review

TODAY = date(2026, 6, 13)


def _year_records() -> tuple[list, dict]:
    raw = {
        "a": make_workout(
            "a",
            "Push",
            start="2026-01-10T17:00:00+00:00",
            end="2026-01-10T18:00:00+00:00",
            exercises=[make_exercise("Bench Press (Barbell)", "T-B", [make_set(60, 8)])],
        ),
        "b": make_workout(
            "b",
            "Push",
            start="2026-03-15T17:00:00+00:00",
            end="2026-03-15T18:00:00+00:00",
            exercises=[make_exercise("Bench Press (Barbell)", "T-B", [make_set(70, 5)])],
        ),
        "c": make_workout(
            "c",
            "Pull",
            start="2026-03-20T17:00:00+00:00",
            end="2026-03-20T18:00:00+00:00",
            exercises=[make_exercise("Bent Over Row (Barbell)", "T-ROW", [make_set(50, 8)])],
        ),
    }
    records = build_records(raw)
    return records, exercise_histories(records)


def test_render_year_review_summary() -> None:
    records, histories = _year_records()
    note = render_year_review(2026, records, histories, TODAY)

    assert "# 2026 — Year in Review" in note
    assert "**3** sessions" in note
    assert "## Best month" in note
    assert "**March**" in note  # March (750 kg) beats January (480 kg)
    assert "## Most-trained exercises" in note
    assert "[[Bench Press (Barbell)]]" in note
    assert "## Muscle balance" in note
    # 70x5 beats the 60x8 baseline on weight and est. 1RM -> 2 PRs.
    assert "## PRs (2)" in note
    # the monthly-volume chart is embedded
    assert "Monthly volume" in note
    assert "xychart-beta" in note


def test_generate_year_reviews_one_note_per_year(tmp_path: Path) -> None:
    raw = {
        "a": make_workout(
            "a", start="2025-05-01T17:00:00+00:00", end="2025-05-01T18:00:00+00:00"
        ),
        "b": make_workout(
            "b", start="2026-05-01T17:00:00+00:00", end="2026-05-01T18:00:00+00:00"
        ),
    }
    records = build_records(raw)
    histories = exercise_histories(records)
    writer = VaultWriter(tmp_path)

    changed = generate_year_reviews(writer, records, histories, TODAY)

    assert changed == 2
    assert (tmp_path / "Reviews" / "2025 Year in Review.md").is_file()
    assert (tmp_path / "Reviews" / "2026 Year in Review.md").is_file()


def test_top_exercises_counts_distinct_workouts_not_entries() -> None:
    # the same lift logged twice in ONE workout = one session, volume summed
    raw = {
        "a": make_workout(
            "a",
            start="2026-04-01T17:00:00+00:00",
            end="2026-04-01T18:00:00+00:00",
            exercises=[
                make_exercise("Bench Press (Barbell)", "T-B", [make_set(60, 8)]),
                make_exercise("Bench Press (Barbell)", "T-B", [make_set(80, 5)], 1),
            ],
        )
    }
    records = build_records(raw)
    note = render_year_review(2026, records, exercise_histories(records), TODAY)
    # volume 60*8 + 80*5 = 880; one workout, not two
    assert "880 kg over 1 sessions" in note


def test_best_month_and_top_exercise_tie_breaks_are_stable() -> None:
    raw = {
        "a": make_workout(
            "a",
            start="2026-02-10T17:00:00+00:00",
            end="2026-02-10T18:00:00+00:00",
            exercises=[make_exercise("Zott Press", "T-Z", [make_set(50, 10)])],  # 500
        ),
        "b": make_workout(
            "b",
            start="2026-03-10T17:00:00+00:00",
            end="2026-03-10T18:00:00+00:00",
            exercises=[make_exercise("Alpha Curl", "T-A", [make_set(50, 10)])],  # 500
        ),
    }
    records = build_records(raw)
    note = render_year_review(2026, records, exercise_histories(records), TODAY)
    assert "**February**" in note  # volume tie -> earliest month
    assert note.index("[[Alpha Curl]]") < note.index("[[Zott Press]]")  # tie -> title


def test_year_with_zero_volume_omits_chart() -> None:
    raw = {
        "a": make_workout(
            "a",
            start="2026-05-01T17:00:00+00:00",
            end="2026-05-01T18:00:00+00:00",
            exercises=[make_exercise("Plank", "T-P", [make_set(None, 60)])],
        )
    }
    records = build_records(raw)
    note = render_year_review(2026, records, exercise_histories(records), TODAY)
    assert "xychart-beta" not in note  # all-zero monthly series -> no chart
    assert "Monthly volume" not in note  # and no orphan heading
    assert "# 2026 — Year in Review" in note  # the rest still renders
    assert "## PRs (0)" in note


def test_render_year_review_handles_year_with_no_prs() -> None:
    raw = {
        "a": make_workout(
            "a", start="2026-02-02T17:00:00+00:00", end="2026-02-02T18:00:00+00:00"
        )
    }
    records = build_records(raw)
    histories = exercise_histories(records)

    note = render_year_review(2026, records, histories, TODAY)

    assert "## PRs (0)" in note
    assert "No PRs recorded this year." in note
