"""Local JSON cache of everything fetched from Hevy.

The cache is the source of truth for vault generation and analytics, so the
vault can be rebuilt offline and history survives even if Hevy ever loses it.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

_WORKOUTS_FILE = "workouts.json"
_ARCHIVED_FILE = "archived_workouts.json"
_MEASUREMENTS_FILE = "measurements.json"
_TEMPLATES_FILE = "exercise_templates.json"
_META_FILE = "meta.json"


def _atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON atomically (temp file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
        tmp_path.replace(path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


class CacheStore:
    """File-backed store for raw Hevy data."""

    def __init__(self, data_dir: Path) -> None:
        """Load existing cache files from data_dir (created on save)."""
        self._dir = data_dir
        self.workouts: dict[str, dict[str, Any]] = _load_json(
            data_dir / _WORKOUTS_FILE, {}
        )
        self.archived: dict[str, dict[str, Any]] = _load_json(
            data_dir / _ARCHIVED_FILE, {}
        )
        self.measurements: list[dict[str, Any]] = _load_json(
            data_dir / _MEASUREMENTS_FILE, []
        )
        self.exercise_templates: dict[str, dict[str, Any]] = _load_json(
            data_dir / _TEMPLATES_FILE, {}
        )
        self.meta: dict[str, Any] = _load_json(data_dir / _META_FILE, {})

    def upsert_workout(self, workout: dict[str, Any]) -> str:
        """Insert or update a raw workout. Returns 'added' or 'updated'."""
        workout_id = workout["id"]
        status = "updated" if workout_id in self.workouts else "added"
        self.workouts[workout_id] = workout
        return status

    def archive_workout(self, workout_id: str) -> bool:
        """Move a workout to the archive (deleted in Hevy). Never destroys data."""
        workout = self.workouts.pop(workout_id, None)
        if workout is None:
            return False
        self.archived[workout_id] = workout
        return True

    def set_measurements(self, measurements: list[dict[str, Any]]) -> None:
        """Replace the measurement list, deduplicated by date, sorted.

        Last write wins: if the API returns several entries for one date,
        the final one silently replaces the rest.
        """
        by_date = {m.get("date"): m for m in measurements if m.get("date")}
        self.measurements = [by_date[d] for d in sorted(by_date)]

    def save(self) -> None:
        """Persist all cache files atomically."""
        _atomic_write_json(self._dir / _WORKOUTS_FILE, self.workouts)
        _atomic_write_json(self._dir / _ARCHIVED_FILE, self.archived)
        _atomic_write_json(self._dir / _MEASUREMENTS_FILE, self.measurements)
        _atomic_write_json(self._dir / _TEMPLATES_FILE, self.exercise_templates)
        # Meta LAST — load-bearing. If a save dies on a data file above, the
        # on-disk events cursor stays old and the next sync replays the same
        # events (upserts are idempotent). Meta-first would advance the cursor
        # past data that was never written, silently losing those events.
        _atomic_write_json(self._dir / _META_FILE, self.meta)
