"""Tests for the A6 Dataview/Bases starter pack (vault.queries)."""

from __future__ import annotations

import yaml

from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.models import build_records
from hevy_brain.vault import queries
from hevy_brain.vault.exercises import render_exercise_note
from hevy_brain.vault.workouts import render_workout_note


def _frontmatter(note: str) -> dict:
    block = note.split("---", 2)[1]
    return yaml.safe_load(block)


def test_render_queries_is_static() -> None:
    assert queries.render_queries() == queries.render_queries()


def test_queries_reference_real_tags() -> None:
    note = queries.render_queries()
    assert "hevy/queries" in note  # its own tag
    for tag in (
        "#hevy/workout",
        "#hevy/exercise",
        "#hevy/review/weekly",
        "#hevy/review/monthly",
    ):
        assert tag in note
    assert note.count("```dataview") >= 6


def test_query_fields_exist_in_real_workout_frontmatter(raw_workouts: dict) -> None:
    """Every workout field the queries TABLE/SORT on must be real frontmatter —
    guards against the queries drifting away from the note schema."""
    records = build_records(raw_workouts)
    keys = _frontmatter(render_workout_note(records[0], [])).keys()
    for field in ("date", "title", "volume_kg", "duration_min", "total_reps", "exercise_count"):
        assert field in keys


def test_query_fields_exist_in_real_exercise_frontmatter(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)
    note = render_exercise_note(next(iter(histories.values())), {})
    keys = _frontmatter(note).keys()
    for field in ("best_e1rm_kg", "best_weight_kg", "times_performed", "last_performed", "total_volume_kg"):
        assert field in keys
