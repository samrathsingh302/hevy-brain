"""Tests for the process-wide cache lock that serialises concurrent writers."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from hevy_brain import cli
from hevy_brain.config import load_config
from hevy_brain.store import cache
from hevy_brain.store.cache import CacheLockBusyError, CacheStore, cache_lock


def test_lock_acquires_and_releases(tmp_path: Path) -> None:
    # Acquire then release; a released lock is immediately reusable.
    with cache_lock(tmp_path):
        pass
    with cache_lock(tmp_path):
        pass


def test_second_acquire_while_held_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # While one holder is inside the lock, a second acquire raises (two separate
    # open file descriptions conflict even within one process) — so the
    # overlapping hourly-sync / Sunday-coach can never both be in the RMW window.
    monkeypatch.setattr(cache, "LOCK_WAIT_SECONDS", 0)
    with cache_lock(tmp_path), pytest.raises(CacheLockBusyError), cache_lock(tmp_path):
        pass


def test_lock_is_reusable_after_a_busy_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A failed (busy) acquire must not strand the original lock or the file.
    monkeypatch.setattr(cache, "LOCK_WAIT_SECONDS", 0)
    with cache_lock(tmp_path), pytest.raises(CacheLockBusyError), cache_lock(tmp_path):
        pass
    # Outer released cleanly -> a fresh acquire still works.
    with cache_lock(tmp_path):
        pass


def test_save_works_under_the_lock(tmp_path: Path) -> None:
    # The happy path: a normal load-modify-save still works while holding it.
    with cache_lock(tmp_path):
        store = CacheStore(tmp_path)
        store.upsert_workout({"id": "w1", "title": "Push", "exercises": []})
        store.save()
    assert CacheStore(tmp_path).workouts["w1"]["title"] == "Push"


def test_lock_creates_missing_data_dir(tmp_path: Path) -> None:
    # data_dir may not exist on a first run.
    fresh = tmp_path / "not-created-yet"
    with cache_lock(fresh):
        pass
    assert fresh.is_dir()


def test_main_writer_command_skips_when_lock_is_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The user-facing contract: a writer command (`sync`) run while another
    # holder has the lock skips cleanly (exit 0 + message) instead of clobbering.
    # sync's network/save path is never reached — the skip happens at dispatch.
    cfg = load_config(base_dir=tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda **_kwargs: cfg)
    monkeypatch.setattr(cache, "LOCK_WAIT_SECONDS", 0)
    with cache_lock(cfg.data_dir):
        rc = cli.main(["sync"])
    assert rc == 0
    assert "in progress" in capsys.readouterr().err.lower()


def test_busy_lock_with_zero_wait_raises_at_once(tmp_path: Path) -> None:
    # wait_seconds=0 is the old non-blocking behaviour: one attempt, then raise.
    with cache_lock(tmp_path):
        started = time.monotonic()
        with pytest.raises(CacheLockBusyError), cache_lock(tmp_path, wait_seconds=0):
            pass
        assert time.monotonic() - started < 1.0


def test_busy_lock_is_acquired_once_the_holder_releases(tmp_path: Path) -> None:
    # The lock loser waits (bounded) instead of skipping: a holder that releases
    # within the wait lets the second acquire through, so the Sunday coach is
    # never lost to the hourly sync that fired with it.
    held = threading.Event()

    def hold_briefly() -> None:
        with cache_lock(tmp_path):
            held.set()
            time.sleep(0.2)

    holder = threading.Thread(target=hold_briefly)
    holder.start()
    try:
        assert held.wait(5)
        with cache_lock(tmp_path, wait_seconds=2, poll_seconds=0.05):
            acquired = True
    finally:
        holder.join()
    assert acquired
