"""Sync engine: full-history backfill plus incremental updates.

First run paginates the entire workout history. Subsequent runs use the
``/workouts/events`` endpoint with a persisted cursor (same approach the
original HA coordinator used) so only changes are fetched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .api.client import HevyApiClient, HevyApiClientError
from .models import parse_iso
from .store.cache import CacheStore

LOGGER = logging.getLogger(__name__)

_MAX_PAGES = 10_000  # runaway-pagination guard


@dataclass
class SyncResult:
    """Summary of one sync run."""

    full_backfill: bool = False
    added: int = 0
    updated: int = 0
    deleted: int = 0
    measurements: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        """Whether any workout data changed."""
        return bool(self.added or self.updated or self.deleted)


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _newest_timestamp(values: Any) -> str | None:
    """Return the most recent ISO timestamp from an iterable (None-tolerant).

    Comparison happens on parsed datetimes so mixed offset spellings still
    order correctly, but the *original server string* is returned — the cursor
    must round-trip to ``/workouts/events?since=`` exactly as Hevy issued it.
    """
    best: str | None = None
    best_dt: datetime | None = None
    for value in values:
        parsed = parse_iso(value)
        if parsed is None:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        if best_dt is None or parsed > best_dt:
            best, best_dt = value, parsed
    return best


async def _paginate(
    fetch: Any, list_key: str, page_size: int, **kwargs: Any
) -> list[dict[str, Any]]:
    """Drain a paginated Hevy endpoint into a single list."""
    items: list[dict[str, Any]] = []
    page = 1
    while page <= _MAX_PAGES:
        response = await fetch(page=page, page_size=page_size, **kwargs)
        batch = response.get(list_key, [])
        items.extend(batch)
        page_count = response.get("page_count")
        if not batch or (page_count is not None and page >= page_count):
            break
        page += 1
    return items


async def full_backfill(
    client: HevyApiClient, store: CacheStore, page_size: int = 10
) -> SyncResult:
    """Fetch the complete workout history into the cache."""
    result = SyncResult(full_backfill=True)
    workouts = await _paginate(client.async_get_workouts, "workouts", page_size)
    for workout in workouts:
        status = store.upsert_workout(workout)
        if status == "added":
            result.added += 1
        else:
            result.updated += 1
    # Seed the events cursor from the newest server-side timestamp, NOT local
    # utcnow: anything created server-side between fetch and stamp would fall
    # before a utcnow cursor and be skipped forever. Replaying the newest
    # item is harmless (upserts are idempotent by id).
    cursor = _newest_timestamp(w.get("updated_at") for w in workouts)
    store.meta["events_cursor"] = cursor or _utcnow_iso()
    store.meta["last_full_sync"] = _utcnow_iso()
    return result


async def incremental_sync(client: HevyApiClient, store: CacheStore) -> SyncResult:
    """Apply workout events (updated/deleted) since the persisted cursor."""
    result = SyncResult()
    cursor = store.meta["events_cursor"]
    events = await _paginate(
        client.async_get_workout_events, "events", 10, since=cursor
    )
    for event in events:
        event_type = event.get("type")
        if event_type == "updated":
            workout = event.get("workout") or {}
            if workout.get("id"):
                status = store.upsert_workout(workout)
                if status == "added":
                    result.added += 1
                else:
                    result.updated += 1
        elif event_type == "deleted":
            workout_id = event.get("id") or (event.get("workout") or {}).get("id")
            if workout_id and store.archive_workout(workout_id):
                result.deleted += 1
    # Advance the cursor only as far as the server itself has seen (newest
    # event timestamp). A utcnow stamp would skip events created between the
    # fetch and the stamp; no events means the cursor stays put.
    newest = _newest_timestamp(
        (event.get("workout") or {}).get("updated_at") or event.get("deleted_at")
        for event in events
    )
    if newest is not None:
        store.meta["events_cursor"] = newest
    return result


async def _refresh_side_data(
    client: HevyApiClient, store: CacheStore, result: SyncResult
) -> None:
    """Refresh measurements, user info, exercise templates (non-fatal)."""
    try:
        measurements = await _paginate(
            client.async_get_body_measurements, "body_measurements", 10
        )
        store.set_measurements(measurements)
        result.measurements = len(measurements)
    except HevyApiClientError as err:
        result.errors.append(f"measurements: {err}")
        LOGGER.warning("Failed to refresh measurements: %s", err)

    try:
        user = await client.async_get_user_info()
        store.meta["user"] = (user or {}).get("data") or {}
    except HevyApiClientError as err:
        result.errors.append(f"user_info: {err}")
        LOGGER.warning("Failed to refresh user info: %s", err)

    try:
        templates = await _paginate(
            client.async_get_exercise_templates, "exercise_templates", 100
        )
        if templates:
            store.exercise_templates = {t["id"]: t for t in templates if t.get("id")}
    except HevyApiClientError as err:
        result.errors.append(f"exercise_templates: {err}")
        LOGGER.warning("Failed to refresh exercise templates: %s", err)


async def sync(
    client: HevyApiClient, store: CacheStore, page_size: int = 10
) -> SyncResult:
    """Run a full or incremental sync depending on cache state, then save.

    Meta state (events cursor, sync timestamps, user info) only stays
    advanced once ``store.save()`` has succeeded: on any failure the whole
    in-memory meta dict is rolled back, so a retry replays the same events
    (upserts are idempotent by id) instead of silently skipping whatever
    this run failed to persist.
    """
    # Shallow copy is enough: sync only ever assigns fresh top-level values.
    # Restore in place — cli.py and vault/build.py hold references to meta.
    previous_meta = dict(store.meta)
    try:
        if not store.workouts or "events_cursor" not in store.meta:
            result = await full_backfill(client, store, page_size=page_size)
        else:
            result = await incremental_sync(client, store)
        await _refresh_side_data(client, store, result)
        store.meta["last_sync"] = _utcnow_iso()
        store.save()
    except BaseException:
        store.meta.clear()
        store.meta.update(previous_meta)
        raise
    return result
