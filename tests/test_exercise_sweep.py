"""Stale exercise notes are archived by build_vault, never deleted."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from hevy_brain.config import Config
from hevy_brain.store.cache import CacheStore
from hevy_brain.vault.build import build_vault
from hevy_brain.vault.writer import MANAGED_MARKER

TODAY = date(2026, 6, 10)

# A note hevy-brain wrote for an exercise that no longer has a history
# (renamed or deleted in Hevy), with a user's own line below the marker.
STALE_NOTE = f"""\
---
exercise: Old Name
times_performed: 3
tags:
- hevy/exercise
---
# Old Name

{MANAGED_MARKER}
my own notes on this lift
"""

# A file the user made under Exercises/ — no managed marker.
USER_NOTE = """\
---
exercise: My Own Lift
---
# My Own Lift

Hand-written, not hevy-brain's.
"""


def _setup(tmp_path: Path, raw_workouts: dict) -> tuple[Config, CacheStore]:
    config = Config(
        base_dir=tmp_path, vault_path=tmp_path / "vault", data_dir=tmp_path / "data"
    )
    store = CacheStore(tmp_path / "data")
    for workout in raw_workouts.values():
        store.upsert_workout(workout)
    exercises_dir = config.vault_root / "Exercises"
    exercises_dir.mkdir(parents=True)
    (exercises_dir / "Old Name.md").write_text(STALE_NOTE, encoding="utf-8")
    (exercises_dir / "My Own Lift.md").write_text(USER_NOTE, encoding="utf-8")
    return config, store


def _build(tmp_path: Path, raw_workouts: dict) -> tuple[Path, dict[str, int]]:
    config, store = _setup(tmp_path, raw_workouts)
    return config.vault_root, build_vault(config, store, today=TODAY)


def test_stale_managed_exercise_note_is_archived(
    tmp_path: Path, raw_workouts: dict
) -> None:
    root, changed = _build(tmp_path, raw_workouts)

    assert not (root / "Exercises" / "Old Name.md").exists()
    archived = root / "Archive" / "Old Name.md"
    assert archived.read_text(encoding="utf-8") == STALE_NOTE
    assert changed["archived"] == 1


def test_unmanaged_file_under_exercises_is_left_alone(
    tmp_path: Path, raw_workouts: dict
) -> None:
    root, _ = _build(tmp_path, raw_workouts)

    assert (root / "Exercises" / "My Own Lift.md").read_text(
        encoding="utf-8"
    ) == USER_NOTE
    assert not (root / "Archive" / "My Own Lift.md").exists()


def test_current_exercise_note_is_untouched(tmp_path: Path, raw_workouts: dict) -> None:
    config, store = _setup(tmp_path, raw_workouts)
    build_vault(config, store, today=TODAY)
    root = config.vault_root
    note = root / "Exercises" / "Bench Press (Barbell).md"
    before = note.read_text(encoding="utf-8")

    second = build_vault(config, store, today=TODAY)

    assert note.read_text(encoding="utf-8") == before
    assert "exercise: Bench Press (Barbell)" in before
    assert not (root / "Archive" / "Bench Press (Barbell).md").exists()
    assert second["archived"] == 0
