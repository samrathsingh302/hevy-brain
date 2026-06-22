"""Tests for the process-wide cache lock that serialises concurrent writers."""

from __future__ import annotations

from pathlib import Path

import pytest

from hevy_brain import cli
from hevy_brain.config import load_config
from hevy_brain.store.cache import CacheLockBusyError, CacheStore, cache_lock


def test_lock_acquires_and_releases(tmp_path: Path) -> None:
    # Acquire then release; a released lock is immediately reusable.
    with cache_lock(tmp_path):
        pass
    with cache_lock(tmp_path):
        pass


def test_second_acquire_while_held_raises(tmp_path: Path) -> None:
    # While one holder is inside the lock, a second acquire raises (two separate
    # open file descriptions conflict even within one process) — so the
    # overlapping hourly-sync / Sunday-coach can never both be in the RMW window.
    with cache_lock(tmp_path), pytest.raises(CacheLockBusyError), cache_lock(tmp_path):
        pass


def test_lock_is_reusable_after_a_busy_failure(tmp_path: Path) -> None:
    # A failed (busy) acquire must not strand the original lock or the file.
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
    with cache_lock(cfg.data_dir):
        rc = cli.main(["sync"])
    assert rc == 0
    assert "in progress" in capsys.readouterr().err.lower()
