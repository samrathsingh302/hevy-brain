"""Tests for the S3 export-to-CSV command (hevy_brain.export + CLI wiring).

Offline only: writes a real cache into ``tmp_path`` and exports it; never touches
the real repo ``exports/`` directory or the live account.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from conftest import make_exercise, make_set, make_workout

from hevy_brain import export
from hevy_brain.cli import main
from hevy_brain.models import build_records
from hevy_brain.store.cache import CacheStore


def _cache(tmp_path: Path, workouts: dict[str, dict]) -> None:
    """Persist a raw-workout cache into ``tmp_path/data`` for the CLI to read."""
    store = CacheStore(tmp_path / "data")
    store.workouts = workouts
    store.save()


def _two_workouts() -> dict[str, dict]:
    """A bench session (warm-up + a bodyweight None-weight set) then a row session."""
    w1 = make_workout(
        "w1",
        "Push Day",
        start="2026-05-25T17:00:00+00:00",
        end="2026-05-25T18:00:00+00:00",
        exercises=[
            make_exercise(
                "Bench Press (Barbell)",
                "T-BENCH",
                sets=[
                    make_set(40, 10, type="warmup"),
                    make_set(60, 8, rpe=8.0),
                ],
            ),
            make_exercise(
                "Pull Up",
                "T-PULLUP",
                sets=[make_set(weight_kg=None, reps=12)],
                index=1,
            ),
        ],
    )
    w2 = make_workout(
        "w2",
        "Pull Day",
        start="2026-06-01T17:00:00+00:00",
        end="2026-06-01T18:10:00+00:00",
        exercises=[
            make_exercise("Bent Over Row (Barbell)", "T-ROW", [make_set(70, 10)]),
        ],
    )
    return {w["id"]: w for w in (w1, w2)}


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return rows[0], rows[1:]


# --- exporter functions -------------------------------------------------------


def test_workout_rows_headers_and_known_row() -> None:
    records = build_records(_two_workouts())
    out = export.default_out_path(Path("/x"), "workouts")
    assert out == Path("/x/exports/hevy-workouts.csv")

    rows = export.workout_rows(records)
    assert [r["hevy_id"] for r in rows] == ["w1", "w2"]  # chronological
    first = rows[0]
    assert first["date"] == "2026-05-25"
    assert first["title"] == "Push Day"
    assert first["duration_min"] == 60
    assert first["total_reps"] == 30  # 10 + 8 + 12
    assert first["exercise_count"] == 2


def test_set_rows_include_warmup_and_none_weight() -> None:
    records = build_records(_two_workouts())
    rows = export.set_rows(records)

    warmup = rows[0]
    assert warmup["set_type"] == "warmup"
    assert warmup["set_index"] == 1
    assert warmup["exercise"] == "Bench Press (Barbell)"

    working = rows[1]
    assert working["set_index"] == 2
    assert working["rpe"] == 8.0

    bodyweight = rows[2]
    assert bodyweight["exercise"] == "Pull Up"
    assert bodyweight["set_index"] == 1  # 1-based within its own exercise
    assert bodyweight["weight_kg"] is None  # real None, serialised empty later


def test_none_serialises_as_empty_cell_not_the_string_none(tmp_path: Path) -> None:
    records = build_records(_two_workouts())
    out = tmp_path / "sets.csv"
    written, count = export.export_csv(records, "sets", out)
    assert written == out.resolve()
    assert count == 4

    header, data = _read_csv(out)
    assert header == export.SET_FIELDS
    # The Pull Up set has weight_kg=None -> empty string, never "None".
    pull_up = next(row for row in data if row[2] == "Pull Up")
    weight_col = header.index("weight_kg")
    rpe_col = header.index("rpe")
    assert pull_up[weight_col] == ""
    assert pull_up[rpe_col] == ""  # no RPE logged -> empty, not "None"
    assert "None" not in [cell for row in data for cell in row]


def test_export_workouts_writes_valid_csv(tmp_path: Path) -> None:
    records = build_records(_two_workouts())
    out = tmp_path / "workouts.csv"
    _, count = export.export_csv(records, "workouts", out)
    assert count == 2
    header, data = _read_csv(out)
    assert header == export.WORKOUT_FIELDS
    assert data[0][header.index("hevy_id")] == "w1"


def test_empty_cache_writes_header_only(tmp_path: Path) -> None:
    out = tmp_path / "empty.csv"
    _, count = export.export_csv([], "sets", out)
    assert count == 0
    header, data = _read_csv(out)
    assert header == export.SET_FIELDS
    assert data == []


# --- CLI wiring ---------------------------------------------------------------


def test_cli_export_default_path_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No --out: writes <base_dir>/exports/hevy-<kind>.csv, OUTSIDE the vault."""
    monkeypatch.chdir(tmp_path)
    _cache(tmp_path, _two_workouts())

    rc = main(["export", "--csv", "--kind", "sets"])
    assert rc == 0

    out = tmp_path / "exports" / "hevy-sets.csv"
    assert out.is_file()
    # Never inside the vault subfolder.
    assert "Hevy" not in out.parts
    header, data = _read_csv(out)
    assert header == export.SET_FIELDS
    assert len(data) == 4


def test_cli_export_honours_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _cache(tmp_path, _two_workouts())
    target = tmp_path / "custom" / "mine.csv"

    rc = main(["export", "--csv", "--out", str(target)])  # default kind = workouts
    assert rc == 0
    assert target.is_file()
    assert not (tmp_path / "exports").exists()  # default dir untouched when --out given

    header, _ = _read_csv(target)
    assert header == export.WORKOUT_FIELDS
    captured = capsys.readouterr()
    assert str(target.resolve()) in captured.out
    assert "2 workouts rows" in captured.out


def test_cli_export_empty_cache_exit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _cache(tmp_path, {})  # empty cache on disk

    rc = main(["export", "--csv", "--kind", "workouts"])
    assert rc == 0  # exporting nothing is not a failure
    out = tmp_path / "exports" / "hevy-workouts.csv"
    header, data = _read_csv(out)
    assert header == export.WORKOUT_FIELDS
    assert data == []
    assert "No workouts to export" in capsys.readouterr().out
