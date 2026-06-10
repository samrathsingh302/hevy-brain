"""Vault build orchestrator: cache -> full set of Obsidian notes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..analytics.prs import exercise_histories
from ..config import Config
from ..models import build_records
from ..store.cache import CacheStore
from . import dashboards, exercises, workouts
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

    changed = {
        "workouts": workouts.generate_workout_notes(writer, records, histories),
        "exercises": exercises.generate_exercise_notes(
            writer, histories, workout_paths
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
                ),
            )
        ),
        "measurements": int(
            writer.write(
                "Measurements/Body Log.md",
                dashboards.render_body_log(store.measurements, today),
            )
        ),
    }

    # Archive notes belonging to workouts deleted in Hevy.
    archived_records = build_records(store.archived)
    archived_paths = workouts.workout_note_paths(archived_records)
    archived_count = 0
    for rel_path in archived_paths.values():
        if writer.archive(rel_path):
            archived_count += 1
    changed["archived"] = archived_count
    return changed
