"""Tests for the local JSON cache."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import make_workout

from hevy_brain.store import cache
from hevy_brain.store.cache import CacheStore


def test_roundtrip(tmp_path: Path) -> None:
    store = CacheStore(tmp_path / "data")
    store.upsert_workout(make_workout("w1"))
    store.set_measurements([{"date": "2026-06-01", "weight_kg": 78.0}])
    store.meta["events_cursor"] = "2026-06-09T00:00:00+00:00"
    store.save()

    reloaded = CacheStore(tmp_path / "data")
    assert "w1" in reloaded.workouts
    assert reloaded.measurements[0]["weight_kg"] == 78.0
    assert reloaded.meta["events_cursor"] == "2026-06-09T00:00:00+00:00"


def test_upsert_distinguishes_added_and_updated(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    assert store.upsert_workout(make_workout("w1")) == "added"
    assert store.upsert_workout(make_workout("w1", title="Renamed")) == "updated"
    assert store.workouts["w1"]["title"] == "Renamed"


def test_archive_moves_not_deletes(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    store.upsert_workout(make_workout("w1"))

    assert store.archive_workout("w1") is True
    assert "w1" not in store.workouts
    assert "w1" in store.archived
    assert store.archive_workout("missing") is False


def test_save_writes_meta_last_so_partial_save_keeps_old_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: meta.json must be the LAST file save() writes. If a save
    dies on an earlier data file, the on-disk cursor must stay old so the
    next sync replays events instead of skipping past unsaved data."""
    store = CacheStore(tmp_path)
    store.meta["events_cursor"] = "2026-06-09T00:00:00+00:00"
    store.save()

    real_write = cache._atomic_write_json

    def explode_on_measurements(path: Path, payload: object) -> None:
        if path.name == "measurements.json":
            raise OSError("boom")
        real_write(path, payload)

    monkeypatch.setattr(cache, "_atomic_write_json", explode_on_measurements)
    store.upsert_workout(make_workout("w1"))
    store.meta["events_cursor"] = "2026-06-10T00:00:00+00:00"
    with pytest.raises(OSError, match="boom"):
        store.save()

    on_disk = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert on_disk["events_cursor"] == "2026-06-09T00:00:00+00:00"


def test_measurements_deduped_by_date_and_sorted(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    store.set_measurements(
        [
            {"date": "2026-06-05", "weight_kg": 78.5},
            {"date": "2026-06-01", "weight_kg": 79.0},
            {"date": "2026-06-05", "weight_kg": 78.2},
        ]
    )
    assert [m["date"] for m in store.measurements] == ["2026-06-01", "2026-06-05"]
    assert store.measurements[1]["weight_kg"] == 78.2
