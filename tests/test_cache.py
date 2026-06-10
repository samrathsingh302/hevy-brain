"""Tests for the local JSON cache."""

from __future__ import annotations

from pathlib import Path

from conftest import make_workout

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
