"""Tests for the sync engine using a fake API client."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import make_workout

from hevy_brain.api.client import HevyApiClientError
from hevy_brain.store.cache import CacheStore
from hevy_brain.sync import sync


class FakeClient:
    """Minimal HevyApiClient stand-in with paginated canned data."""

    def __init__(
        self,
        workouts: list[dict] | None = None,
        events: list[dict] | None = None,
        measurements: list[dict] | None = None,
        templates: list[dict] | None = None,
        page_size_cap: int = 2,
    ) -> None:
        self.workouts = workouts or []
        self.events = events or []
        self.measurements = measurements or []
        self.templates = templates or []
        self._cap = page_size_cap
        self.calls: list[str] = []

    @staticmethod
    def _page(items: list, key: str, page: int, size: int) -> dict[str, Any]:
        pages = max(1, -(-len(items) // size)) if items else 1
        chunk = items[(page - 1) * size : page * size]
        return {key: chunk, "page": page, "page_count": pages}

    async def async_get_workouts(self, page: int = 1, page_size: int = 10) -> dict:
        self.calls.append(f"workouts:{page}")
        return self._page(self.workouts, "workouts", page, min(page_size, self._cap))

    async def async_get_workout_events(
        self, since: str, page: int = 1, page_size: int = 10
    ) -> dict:
        self.calls.append(f"events:{page}:{since}")
        return self._page(self.events, "events", page, page_size)

    async def async_get_body_measurements(
        self, page: int = 1, page_size: int = 10
    ) -> dict:
        return self._page(self.measurements, "body_measurements", page, page_size)

    async def async_get_user_info(self) -> dict:
        return {"data": {"id": "u1", "username": "sam"}}

    async def async_get_exercise_templates(
        self, page: int = 1, page_size: int = 100
    ) -> dict:
        return self._page(self.templates, "exercise_templates", page, page_size)


async def test_first_sync_backfills_all_pages(tmp_path: Path) -> None:
    workouts = [make_workout(f"w{i}") for i in range(5)]
    client = FakeClient(workouts=workouts, page_size_cap=2)
    store = CacheStore(tmp_path)

    result = await sync(client, store)

    assert result.full_backfill is True
    assert result.added == 5
    assert len(store.workouts) == 5
    assert "events_cursor" in store.meta
    # paginated: 5 workouts at 2/page = 3 pages
    assert [c for c in client.calls if c.startswith("workouts")] == [
        "workouts:1",
        "workouts:2",
        "workouts:3",
    ]


async def test_second_sync_is_incremental_and_idempotent(tmp_path: Path) -> None:
    client = FakeClient(workouts=[make_workout("w1")])
    store = CacheStore(tmp_path)
    await sync(client, store)

    result = await sync(client, store)

    assert result.full_backfill is False
    assert not result.changed
    assert len(store.workouts) == 1


async def test_incremental_applies_updates_and_deletes(tmp_path: Path) -> None:
    client = FakeClient(workouts=[make_workout("w1"), make_workout("w2")])
    store = CacheStore(tmp_path)
    await sync(client, store)

    client.events = [
        {"type": "updated", "workout": make_workout("w1", title="Edited")},
        {"type": "updated", "workout": make_workout("w9", title="Brand New")},
        {"type": "deleted", "id": "w2"},
    ]
    result = await sync(client, store)

    assert result.updated == 1
    assert result.added == 1
    assert result.deleted == 1
    assert store.workouts["w1"]["title"] == "Edited"
    assert "w9" in store.workouts
    assert "w2" in store.archived


async def test_side_data_failures_are_non_fatal(tmp_path: Path) -> None:
    class FlakyClient(FakeClient):
        async def async_get_body_measurements(self, page=1, page_size=10):
            raise HevyApiClientError("boom")

        async def async_get_user_info(self):
            raise HevyApiClientError("boom")

    client = FlakyClient(workouts=[make_workout("w1")])
    store = CacheStore(tmp_path)

    result = await sync(client, store)

    assert len(store.workouts) == 1
    assert len(result.errors) == 2


class ExplodingClient(FakeClient):
    """Fails after event processing with an error the sync does not absorb."""

    async def async_get_user_info(self) -> dict:
        raise RuntimeError("boom")


async def test_failed_sync_does_not_advance_cursor(tmp_path: Path) -> None:
    """Regression: an exception between event-processing and save must leave
    the events cursor untouched (memory + disk) so a retry replays the same
    events instead of skipping them."""
    client = FakeClient(workouts=[make_workout("w1")])
    store = CacheStore(tmp_path)
    await sync(client, store)
    cursor_before = store.meta["events_cursor"]
    meta_before = dict(store.meta)

    failing = ExplodingClient(
        events=[{"type": "updated", "workout": make_workout("w2", title="New")}]
    )
    with pytest.raises(RuntimeError):
        await sync(failing, store)

    assert store.meta["events_cursor"] == cursor_before
    assert CacheStore(tmp_path).meta["events_cursor"] == cursor_before
    # The sync timestamps must roll back along with the cursor.
    assert store.meta == meta_before

    # Retry from disk (fresh process): the failed run persisted nothing, so
    # the same events replay cleanly and exactly once.
    retry_store = CacheStore(tmp_path)
    assert "w2" not in retry_store.workouts
    result = await sync(FakeClient(events=failing.events), retry_store)
    assert result.added == 1
    assert len(retry_store.workouts) == 2
    assert (
        CacheStore(tmp_path).meta["events_cursor"] == retry_store.meta["events_cursor"]
    )


async def test_failed_first_sync_leaves_no_cursor(tmp_path: Path) -> None:
    """A failed initial backfill must not leave a seeded cursor behind, or the
    next run would sync incrementally from a backfill that was never saved."""
    store = CacheStore(tmp_path)

    with pytest.raises(RuntimeError):
        await sync(ExplodingClient(workouts=[make_workout("w1")]), store)

    assert "events_cursor" not in store.meta
    # last_full_sync (and everything else meta) must roll back too.
    assert store.meta == {}


async def test_failed_save_rolls_back_meta_timestamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: ``last_sync`` is stamped just before ``store.save()``, so a
    failing save is the only path that can leave it advanced in memory. The
    whole meta dict must match its pre-sync state, on disk and in memory."""
    store = CacheStore(tmp_path)
    await sync(FakeClient(workouts=[make_workout("w1")]), store)
    meta_before = dict(store.meta)

    def explode() -> None:
        raise OSError("boom")

    monkeypatch.setattr(store, "save", explode)
    with pytest.raises(OSError, match="boom"):
        await sync(FakeClient(), store)

    assert store.meta == meta_before
    assert CacheStore(tmp_path).meta == meta_before


async def test_measurements_and_templates_cached(tmp_path: Path) -> None:
    client = FakeClient(
        workouts=[make_workout("w1")],
        measurements=[{"date": "2026-06-01", "weight_kg": 78.0}],
        templates=[
            {
                "id": "T-BENCH",
                "title": "Bench Press (Barbell)",
                "primary_muscle_group": "chest",
            }
        ],
    )
    store = CacheStore(tmp_path)

    await sync(client, store)

    assert store.measurements[0]["date"] == "2026-06-01"
    assert store.exercise_templates["T-BENCH"]["primary_muscle_group"] == "chest"
    assert store.meta["user"]["username"] == "sam"
