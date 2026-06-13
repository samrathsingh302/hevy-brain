"""Tests for routine notes in the vault."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from conftest import make_routine, make_routine_exercise, make_routine_set

from hevy_brain.config import Config
from hevy_brain.store.cache import CacheStore
from hevy_brain.vault.build import build_vault
from hevy_brain.vault.routines import routine_note_paths

TODAY = date(2026, 6, 12)


def _config(tmp_path: Path) -> Config:
    return Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )


def _store(tmp_path: Path, routines: list[dict]) -> CacheStore:
    store = CacheStore(tmp_path / "data")
    store.set_routines(routines)
    store.routine_folders = {"7": {"id": 7, "title": "PPL"}}
    return store


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def test_routine_note_rendered_with_roundtrip_frontmatter(tmp_path: Path) -> None:
    routine = make_routine(
        "r1",
        folder_id=7,
        exercises=[
            make_routine_exercise(
                sets=[
                    make_routine_set(60, 8),
                    make_routine_set(
                        65, None, rep_range={"start": 5, "end": 8}, type="failure"
                    ),
                ]
            )
        ],
    )
    config = _config(tmp_path)
    store = _store(tmp_path, [routine])

    changed = build_vault(config, store, today=TODAY)

    note = config.vault_root / "Routines" / "Push Day A.md"
    assert changed["routines"] == 1
    assert note.is_file()

    data = _frontmatter(note)
    assert data["type"] == "hevy-routine"
    assert data["hevy_routine_id"] == "r1"
    assert data["folder"] == "PPL"
    bench = data["exercises"][0]
    assert bench["exercise_template_id"] == "T-BENCH"
    assert bench["rest_seconds"] == 120
    assert bench["sets"][0] == {"type": "normal", "weight_kg": 60, "reps": 8}
    assert bench["sets"][1]["rep_range"] == {"start": 5, "end": 8}

    text = note.read_text(encoding="utf-8")
    assert "[[Bench Press (Barbell)]]" in text
    assert "5–8" in text
    assert "%% hevy-brain:end %%" in text


def test_routine_regen_is_idempotent(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, [make_routine()])

    build_vault(config, store, today=TODAY)
    second = build_vault(config, store, today=TODAY)

    assert second["routines"] == 0


def test_duplicate_routine_titles_get_id_suffix() -> None:
    older = make_routine("aaaa1111", "Push Day")
    older["created_at"] = "2026-04-01T09:00:00+00:00"
    newer = make_routine("bbbb2222", "Push Day")

    paths = routine_note_paths({r["id"]: r for r in (older, newer)})

    assert paths["aaaa1111"] == "Routines/Push Day.md"
    assert paths["bbbb2222"] == "Routines/Push Day (bbbb2222).md"


def test_deleted_routine_note_archives(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, [make_routine("r1"), make_routine("r2", "Pull Day A")])
    build_vault(config, store, today=TODAY)

    store.set_routines([make_routine("r1")])
    changed = build_vault(config, store, today=TODAY)

    root = config.vault_root
    assert changed["archived"] == 1
    assert not (root / "Routines" / "Pull Day A.md").exists()
    assert (root / "Archive" / "Pull Day A.md").exists()


def test_renamed_routine_archives_old_title_note(tmp_path: Path) -> None:
    """A routine renamed in Hevy (same id, new title — e.g. after a draft
    push) must not leave the old-title note behind forever (live finding,
    13/06/2026: 'upper' lingered after becoming 'Return Week 1 — upper')."""
    config = _config(tmp_path)
    store = _store(tmp_path, [make_routine("r1", "upper")])
    build_vault(config, store, today=TODAY)

    store.set_routines([make_routine("r1", "Return Week 1 — upper")])
    changed = build_vault(config, store, today=TODAY)

    root = config.vault_root
    assert changed["archived"] == 1
    assert not (root / "Routines" / "upper.md").exists()
    assert (root / "Archive" / "upper.md").exists()
    assert (root / "Routines" / "Return Week 1 — upper.md").is_file()


def test_stale_sweep_leaves_user_files_and_drafts_alone(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, [make_routine("r1", "upper")])
    build_vault(config, store, today=TODAY)

    root = config.vault_root
    user_file = root / "Routines" / "my plan ideas.md"
    user_file.write_text("# scratch — not hevy-brain's\n", encoding="utf-8")
    draft = root / "Routines" / "Drafts" / "Return Week 1 — upper.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(
        (root / "Routines" / "upper.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    changed = build_vault(config, store, today=TODAY)

    assert changed["archived"] == 0
    assert user_file.is_file()
    assert draft.is_file()


def test_reused_title_never_archives_the_active_note(tmp_path: Path) -> None:
    """A deleted routine whose title was reused by a newer active routine must
    not drag the active note into Archive/."""
    config = _config(tmp_path)
    store = _store(tmp_path, [make_routine("r1", "Push Day A")])
    build_vault(config, store, today=TODAY)

    store.set_routines([make_routine("r9", "Push Day A")])
    changed = build_vault(config, store, today=TODAY)

    assert changed["archived"] == 0
    note = config.vault_root / "Routines" / "Push Day A.md"
    assert note.is_file()
    assert _frontmatter(note)["hevy_routine_id"] == "r9"
