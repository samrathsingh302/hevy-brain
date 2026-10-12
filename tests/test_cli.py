"""Tests for CLI output configuration and push error handling."""

from __future__ import annotations

import io
import re
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import make_workout

from hevy_brain import cli
from hevy_brain.api.client import HevyApiClientError
from hevy_brain.cli import _configure_output, build_parser
from hevy_brain.clock import LONDON
from hevy_brain.config import load_config
from hevy_brain.store import cache
from hevy_brain.store.cache import CacheStore, cache_lock


def test_configure_output_survives_cp1252_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dry-run diff prints '→'; a cp1252 Windows console must not crash
    (live finding 13/06/2026: the first dry-run died mid-print)."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    _configure_output()
    sys.stdout.write("80kg ×6–8 → 47.5kg ×6–8\n")
    stream.flush()

    assert b"47.5kg" in buffer.getvalue()


def test_configure_output_tolerates_streams_without_reconfigure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    _configure_output()  # must not raise


def _fake_client(monkeypatch: pytest.MonkeyPatch, client: MagicMock) -> None:
    async def fake_with_client(config, runner):
        return await runner(client)

    monkeypatch.setattr(cli, "_with_client", fake_with_client)


async def test_push_measurement_api_error_is_a_sentence_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    client = MagicMock()
    client.async_create_body_measurement = AsyncMock(
        side_effect=HevyApiClientError("HTTP 500 from Hevy")
    )
    _fake_client(monkeypatch, client)
    args = build_parser().parse_args(
        ["push", "measurement", "--date", "2026-10-05", "--weight-kg", "78.4"]
    )

    assert await cli._cmd_push_measurement(MagicMock(), args) == 1

    err = capsys.readouterr().err
    assert "Push failed: HTTP 500 from Hevy" in err
    assert "Traceback" not in err


async def test_push_workout_create_api_error_is_a_sentence_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    file = tmp_path / "planned.md"
    file.write_text(
        "---\n"
        "type: hevy-planned-workout\n"
        "title: Push Day\n"
        "exercises:\n"
        "  - exercise_template_id: T-BENCH\n"
        "    sets:\n"
        "      - { weight_kg: 60, reps: 8 }\n"
        "---\n",
        encoding="utf-8",
    )
    client = MagicMock()
    client.async_create_workout = AsyncMock(
        side_effect=HevyApiClientError("HTTP 400 from Hevy")
    )
    _fake_client(monkeypatch, client)

    assert await cli._cmd_push_workout(MagicMock(), file) == 1

    err = capsys.readouterr().err
    assert "Push failed: HTTP 400 from Hevy" in err
    assert "Traceback" not in err


@pytest.mark.parametrize("bad", ["2026-13-40", "2026-1-5", "20261005", "yesterday"])
def test_push_measurement_rejects_a_non_iso_date_at_parse_time(
    bad: str, capsys: pytest.CaptureFixture
) -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["push", "measurement", "--date", bad])

    assert exc.value.code == 2
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_push_measurement_accepts_an_iso_date() -> None:
    args = build_parser().parse_args(["push", "measurement", "--date", "2026-10-05"])

    assert args.date == "2026-10-05"


def test_summary_lines_carry_a_london_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # WORKFLOW-BUGS 1278: the unattended jobs append these lines to logs/*.log,
    # which can't say when a run happened unless each line is dated.
    cfg = load_config(base_dir=tmp_path)
    store = CacheStore(cfg.data_dir)
    store.upsert_workout(make_workout())
    store.save()
    fixed = datetime(2026, 10, 12, 21, 0, tzinfo=LONDON)
    monkeypatch.setattr(cli, "now_london", lambda: fixed)
    monkeypatch.setattr(cli, "build_vault", lambda _config, _store: {"workouts": 1})

    assert cli._cmd_vault(cfg) == 0

    assert capsys.readouterr().out.startswith("[12/10/2026 21:00:00] Vault updated at")


def test_lock_skip_line_carries_a_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    cfg = load_config(base_dir=tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda **_kwargs: cfg)
    monkeypatch.setattr(cache, "LOCK_WAIT_SECONDS", 0)
    with cache_lock(cfg.data_dir):
        rc = cli.main(["sync"])

    assert rc == 0
    err = capsys.readouterr().err
    assert re.match(r"\[\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}\] Another hevy-brain", err)
