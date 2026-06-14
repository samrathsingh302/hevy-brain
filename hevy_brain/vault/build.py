"""Vault build orchestrator: cache -> full set of Obsidian notes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..analytics.prs import exercise_histories
from ..config import Config
from ..models import build_records
from ..store.cache import CacheStore
from . import dashboards, exercises, queries, routines, workouts, yearreview
from .writer import VaultWriter


def build_vault(
    config: Config, store: CacheStore, today: Any | None = None
) -> dict[str, int]:
    """Regenerate every managed note from the local cache.

    Returns counts of changed files per category. Notes for workouts that
    were deleted in Hevy are moved to Archive/ (never destroyed).
    """
    today = today or datetime.now(tz=UTC).date()
    writer = VaultWriter(config.vault_root)
    config.vault_root.mkdir(parents=True, exist_ok=True)

    records = build_records(store.workouts)
    histories = exercise_histories(records)
    workout_paths = workouts.workout_note_paths(records)

    volume_weeks = config.charts_volume_weeks if config.charts_enabled else 0
    e1rm_points = config.charts_e1rm_points if config.charts_enabled else 0

    changed = {
        "workouts": workouts.generate_workout_notes(writer, records, histories),
        "exercises": exercises.generate_exercise_notes(
            writer, histories, workout_paths, e1rm_max_points=e1rm_points
        ),
        "reviews": dashboards.generate_reviews(
            writer,
            records,
            histories,
            workout_paths,
            today,
            review_weeks=config.review_weeks,
            review_months=config.review_months,
            templates=store.exercise_templates,
            overrides=config.muscle_overrides,
        ),
        "dashboard": int(
            writer.write(
                "Dashboard.md",
                dashboards.render_dashboard(
                    records,
                    histories,
                    workout_paths,
                    store.meta,
                    today,
                    templates=store.exercise_templates,
                    overrides=config.muscle_overrides,
                    volume_weeks=volume_weeks,
                    lapse_nudge_days=config.lapse_nudge_days,
                    guide_lapse_days=config.guide_lapse_days,
                ),
            )
        ),
        "measurements": int(
            writer.write(
                "Measurements/Body Log.md",
                dashboards.render_body_log(store.measurements, histories, today),
            )
        ),
        "queries": int(writer.write("Queries.md", queries.render_queries())),
        "routines": routines.generate_routine_notes(
            writer, store.routines, store.routine_folders
        ),
        "year_reviews": yearreview.generate_year_reviews(
            writer,
            records,
            histories,
            today,
            templates=store.exercise_templates,
            overrides=config.muscle_overrides,
        ),
    }

    # Archive notes belonging to workouts/routines deleted in Hevy.
    archived_records = build_records(store.archived)
    archived_paths = workouts.workout_note_paths(archived_records)
    archived_count = 0
    for rel_path in archived_paths.values():
        if writer.archive(rel_path):
            archived_count += 1
    # A deleted routine's title can since have been reused by an active one
    # at the same path — never archive a path an active routine owns.
    active_routine_paths = set(routines.routine_note_paths(store.routines).values())
    for rel_path in routines.routine_note_paths(store.archived_routines).values():
        if rel_path not in active_routine_paths and writer.archive(rel_path):
            archived_count += 1
    # A routine renamed in Hevy leaves its old-title note behind (the store
    # only remembers deletions) — sweep managed notes no routine owns.
    archived_count += routines.archive_stale_routine_notes(writer, active_routine_paths)
    changed["archived"] = archived_count
    return changed
