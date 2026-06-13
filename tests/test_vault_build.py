"""End-to-end vault generation tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from conftest import make_workout

from hevy_brain.config import Config
from hevy_brain.store.cache import CacheStore
from hevy_brain.vault.build import build_vault
from hevy_brain.vault.workouts import workout_note_paths

TODAY = date(2026, 6, 10)


def _config(tmp_path: Path) -> Config:
    return Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )


def _store(tmp_path: Path, raw_workouts: dict) -> CacheStore:
    store = CacheStore(tmp_path / "data")
    for workout in raw_workouts.values():
        store.upsert_workout(workout)
    store.set_measurements([{"date": "2026-06-01", "weight_kg": 78.0}])
    return store


def test_build_vault_generates_all_notes(tmp_path: Path, raw_workouts: dict) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    changed = build_vault(config, store, today=TODAY)

    root = config.vault_root
    assert changed["workouts"] == 3
    assert (root / "Dashboard.md").is_file()
    assert (root / "Workouts" / "2026-06-08 Push Day.md").is_file()
    assert (root / "Exercises" / "Bench Press (Barbell).md").is_file()
    assert (root / "Measurements" / "Body Log.md").is_file()
    assert list((root / "Reviews").glob("*Weekly Review.md"))

    workout_text = (root / "Workouts" / "2026-06-08 Push Day.md").read_text(
        encoding="utf-8"
    )
    assert "hevy_id: w3" in workout_text
    assert "type: hevy-workout" in workout_text
    assert "[[Bench Press (Barbell)]]" in workout_text
    assert "PR" in workout_text  # w3 sets a bench weight PR
    assert "push workout <file> --update" in workout_text  # fix-up callout

    dashboard = (root / "Dashboard.md").read_text(encoding="utf-8")
    assert "3** workouts" in dashboard or "**3** workouts" in dashboard


def test_generated_workout_note_round_trips(
    tmp_path: Path, raw_workouts: dict
) -> None:
    """A managed workout note from the real build path must parse back into a
    no-op PUT body — the fix-up round-trip guarantee, end to end."""
    from hevy_brain.writeback.hevy_push import parse_workout_note, workout_diff

    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)
    build_vault(config, store, today=TODAY)

    note = config.vault_root / "Workouts" / "2026-06-08 Push Day.md"
    workout_id, body = parse_workout_note(note)

    assert workout_id == "w3"
    assert workout_diff(raw_workouts["w3"], body) == []


def test_build_vault_is_idempotent(tmp_path: Path, raw_workouts: dict) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)
    second = build_vault(config, store, today=TODAY)

    assert sum(second.values()) == 0


def test_archived_workout_note_moves_to_archive(
    tmp_path: Path, raw_workouts: dict
) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)
    build_vault(config, store, today=TODAY)

    store.archive_workout("w2")
    changed = build_vault(config, store, today=TODAY)

    root = config.vault_root
    assert changed["archived"] == 1
    assert not (root / "Workouts" / "2026-06-01 Pull Day.md").exists()
    assert (root / "Archive" / "2026-06-01 Pull Day.md").exists()


def test_duplicate_title_same_day_gets_suffix() -> None:
    w_a = make_workout(
        "aaaa1111",
        "Push Day",
        start="2026-06-08T07:00:00+00:00",
        end="2026-06-08T08:00:00+00:00",
    )
    w_b = make_workout(
        "bbbb2222",
        "Push Day",
        start="2026-06-08T17:00:00+00:00",
        end="2026-06-08T18:00:00+00:00",
    )
    from hevy_brain.models import build_records

    paths = workout_note_paths(build_records({w["id"]: w for w in (w_a, w_b)}))

    assert paths["aaaa1111"] == "Workouts/2026-06-08 Push Day.md"
    assert paths["bbbb2222"] == "Workouts/2026-06-08 Push Day (bbbb2222).md"
