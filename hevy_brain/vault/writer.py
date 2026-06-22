"""Safe markdown writer for the Obsidian vault.

Guarantees:
- never writes outside its root folder (path-traversal protected)
- atomic writes (temp file + rename), UTF-8 without BOM
- idempotent: rewriting identical content is a no-op
- user edits below the managed marker are preserved across regenerations
- never deletes notes: removed workouts are moved to Archive/
"""

from __future__ import annotations

import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

MANAGED_MARKER = "%% hevy-brain:end %%"
# The marker only counts when it STARTS a line — briefing instructions
# mention it inline (in backticks), and a mention must never split the note.
_MARKER_LINE_RE = re.compile(rf"^{re.escape(MANAGED_MARKER)}", re.MULTILINE)

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class VaultPathError(Exception):
    """Raised when a write would land outside the managed vault folder."""


def sanitize_filename(name: str) -> str:
    """Make a string safe as a Windows/Obsidian filename."""
    cleaned = _INVALID_CHARS.sub("", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(".")
    return cleaned or "Untitled"


def render_note(frontmatter: dict[str, Any], body: str) -> str:
    """Render YAML frontmatter + markdown body."""
    yaml_text = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    return f"---\n{yaml_text}---\n\n{body.strip()}\n"


class VaultWriter:
    """Writes managed markdown notes under a single vault folder."""

    def __init__(self, root: Path) -> None:
        """Create the writer rooted at the hevy-brain vault folder."""
        self.root = root.resolve()
        self.written: list[str] = []
        self.failed: list[str] = []

    def _target(self, rel_path: str) -> Path:
        target = (self.root / rel_path).resolve()
        if self.root != target and self.root not in target.parents:
            msg = f"Refusing to write outside vault folder: {rel_path!r}"
            raise VaultPathError(msg)
        return target

    def write(self, rel_path: str, managed_content: str) -> bool:
        """Write a managed note, preserving any user content below the marker.

        Returns True if the file changed on disk.
        """
        target = self._target(rel_path)
        user_tail = "\n"
        existing: str | None = None
        if target.is_file():
            existing = target.read_text(encoding="utf-8")
            match = _MARKER_LINE_RE.search(existing)
            if match:
                user_tail = existing[match.end() :]
                if not user_tail.endswith("\n"):
                    user_tail += "\n"
            else:
                # A file we did not create: keep its content below the marker.
                user_tail = "\n\n" + existing.strip() + "\n"

        new_text = managed_content.strip() + f"\n\n{MANAGED_MARKER}" + user_tail
        if existing == new_text:
            return False

        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(new_text)
            published = self._publish(tmp_path, target)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        # A note held open in Obsidian locks the atomic replace (a Windows
        # share-violation). After the retry budget, skip + record this one note
        # rather than aborting the whole rebuild — the cache is the source of
        # truth, so the next build re-writes it.
        if not published:
            tmp_path.unlink(missing_ok=True)
            self.failed.append(rel_path)
            return False
        self.written.append(rel_path)
        return True

    def _publish(self, tmp_path: Path, target: Path) -> bool:
        """Atomically move ``tmp_path`` onto ``target``, retrying a transient lock.

        Returns True on success; False if the target stayed locked (held open in
        Obsidian) for the whole retry budget. A non-lock OSError propagates.
        """
        attempts = 5
        for attempt in range(attempts):
            try:
                tmp_path.replace(target)
            except PermissionError:
                if attempt == attempts - 1:
                    return False
                time.sleep(0.1)
            else:
                return True
        return False

    def archive(self, rel_path: str, archive_dir: str = "Archive") -> bool:
        """Move a note into the archive folder. Returns True if moved."""
        source = self._target(rel_path)
        if not source.is_file():
            return False
        destination = self._target(f"{archive_dir}/{source.name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            stem, suffix = destination.stem, destination.suffix
            counter = 1
            while destination.exists():
                destination = destination.with_name(f"{stem} ({counter}){suffix}")
                counter += 1
        source.replace(destination)
        return True
