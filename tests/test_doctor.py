"""Tests for the D2 health-check command (hevy_brain.doctor)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hevy_brain import doctor
from hevy_brain.config import Config
from hevy_brain.store.cache import CacheStore

NOW = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)


def _config(tmp_path: Path) -> Config:
    (tmp_path / "vault").mkdir()
    return Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )


def _store(tmp_path: Path, *, synced_hours_ago: float | None = 2) -> CacheStore:
    store = CacheStore(tmp_path / "data")
    store.workouts = {"w1": {"id": "w1"}}
    if synced_hours_ago is not None:
        store.meta = {"last_sync": (NOW - timedelta(hours=synced_hours_ago)).isoformat()}
    return store


def _build_dashboard(config: Config) -> None:
    config.vault_root.mkdir(parents=True, exist_ok=True)
    (config.vault_root / "Dashboard.md").write_text("# Hevy Dashboard\n", encoding="utf-8")


def _status(checks: list, name: str) -> str:
    return next(c.status for c in checks if c.name == name)


@pytest.fixture
def keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEVY_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")


def test_all_healthy(tmp_path: Path, keys: None) -> None:
    config = _config(tmp_path)
    _build_dashboard(config)
    checks = doctor.run_checks(config, _store(tmp_path), NOW)
    assert doctor.worst_status(checks) == doctor.OK


def test_missing_hevy_key_is_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HEVY_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    config = _config(tmp_path)
    _build_dashboard(config)
    checks = doctor.run_checks(config, _store(tmp_path), NOW)
    assert _status(checks, "Hevy API key") == doctor.FAIL
    assert doctor.worst_status(checks) == doctor.FAIL


def test_missing_anthropic_key_is_only_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEVY_API_KEY", "k")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = _config(tmp_path)
    _build_dashboard(config)
    checks = doctor.run_checks(config, _store(tmp_path), NOW)
    assert _status(checks, "Anthropic API key") == doctor.WARN
    assert doctor.worst_status(checks) == doctor.WARN  # nothing failed


def test_empty_cache_is_fail(tmp_path: Path, keys: None) -> None:
    config = _config(tmp_path)
    store = CacheStore(tmp_path / "data")  # no workouts
    assert _status(doctor.run_checks(config, store, NOW), "Cache") == doctor.FAIL


def test_stale_sync_warns(tmp_path: Path, keys: None) -> None:
    config = _config(tmp_path)
    checks = doctor.run_checks(config, _store(tmp_path, synced_hours_ago=30), NOW)
    assert _status(checks, "Sync freshness") == doctor.WARN


def test_never_synced_warns(tmp_path: Path, keys: None) -> None:
    config = _config(tmp_path)
    checks = doctor.run_checks(config, _store(tmp_path, synced_hours_ago=None), NOW)
    assert _status(checks, "Sync freshness") == doctor.WARN


def test_naive_last_sync_is_tolerated(tmp_path: Path, keys: None) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path)
    store.meta = {"last_sync": "2026-06-13T10:00:00"}  # no tz -> assumed UTC
    checks = doctor.run_checks(config, store, NOW)  # 2h ago -> ok, no crash
    assert _status(checks, "Sync freshness") == doctor.OK


def test_missing_vault_path_is_fail(tmp_path: Path, keys: None) -> None:
    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "nope",  # never created
        data_dir=tmp_path / "data",
    )
    assert _status(doctor.run_checks(config, _store(tmp_path), NOW), "Vault path") == doctor.FAIL


def test_unbuilt_vault_warns(tmp_path: Path, keys: None) -> None:
    config = _config(tmp_path)  # vault dir exists, but no Dashboard.md
    checks = doctor.run_checks(config, _store(tmp_path), NOW)
    assert _status(checks, "Vault built") == doctor.WARN


def test_worst_status_precedence() -> None:
    mk = doctor.Check
    assert doctor.worst_status([mk("a", doctor.OK, "")]) == doctor.OK
    assert doctor.worst_status([mk("a", doctor.OK, ""), mk("b", doctor.WARN, "")]) == doctor.WARN
    assert doctor.worst_status([mk("a", doctor.WARN, ""), mk("b", doctor.FAIL, "")]) == doctor.FAIL
