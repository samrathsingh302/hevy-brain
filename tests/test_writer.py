"""Tests for the safe vault writer."""

from __future__ import annotations

from pathlib import Path

import pytest

from hevy_brain.vault.writer import (
    MANAGED_MARKER,
    VaultPathError,
    VaultWriter,
    render_note,
    sanitize_filename,
)


def test_write_and_idempotency(tmp_path: Path) -> None:
    writer = VaultWriter(tmp_path)

    assert writer.write("Workouts/note.md", "# Hello") is True
    text = (tmp_path / "Workouts" / "note.md").read_text(encoding="utf-8")
    assert text.startswith("# Hello")
    assert MANAGED_MARKER in text

    # Identical content -> no-op
    assert writer.write("Workouts/note.md", "# Hello") is False
    # Changed content -> rewrite
    assert writer.write("Workouts/note.md", "# Hello v2") is True


def test_user_content_below_marker_preserved(tmp_path: Path) -> None:
    writer = VaultWriter(tmp_path)
    writer.write("note.md", "# Managed")
    target = tmp_path / "note.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nMy personal thoughts.\n",
        encoding="utf-8",
    )

    writer.write("note.md", "# Managed v2")

    text = target.read_text(encoding="utf-8")
    assert "# Managed v2" in text
    assert "My personal thoughts." in text
    assert text.index(MANAGED_MARKER) < text.index("My personal thoughts.")


def test_existing_unmanaged_file_content_kept(tmp_path: Path) -> None:
    target = tmp_path / "note.md"
    target.write_text("Pre-existing user note.\n", encoding="utf-8")
    writer = VaultWriter(tmp_path)

    writer.write("note.md", "# Managed")

    text = target.read_text(encoding="utf-8")
    assert "# Managed" in text
    assert "Pre-existing user note." in text


def test_path_traversal_refused(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    writer = VaultWriter(root)

    with pytest.raises(VaultPathError):
        writer.write("../escape.md", "nope")
    assert not (tmp_path / "escape.md").exists()


def test_archive_moves_note(tmp_path: Path) -> None:
    writer = VaultWriter(tmp_path)
    writer.write("Workouts/old.md", "# Old")

    assert writer.archive("Workouts/old.md") is True
    assert not (tmp_path / "Workouts" / "old.md").exists()
    assert (tmp_path / "Archive" / "old.md").exists()
    assert writer.archive("Workouts/old.md") is False


def test_sanitize_filename() -> None:
    assert sanitize_filename("Push: Day <1>?") == "Push Day 1"
    assert sanitize_filename("a/b\\c") == "abc"
    assert sanitize_filename("   ") == "Untitled"
    assert sanitize_filename("name.") == "name"


def test_render_note_frontmatter() -> None:
    note = render_note({"title": "X", "volume_kg": 1.5}, "Body")
    assert note.startswith("---\n")
    assert "title: X" in note
    assert "volume_kg: 1.5" in note
    assert note.rstrip().endswith("Body")
