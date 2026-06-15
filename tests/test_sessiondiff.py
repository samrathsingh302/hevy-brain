"""Tests for the S4 last-vs-prior session diff (analytics.sessiondiff + CLI).

Offline only: pure-logic tests run on built records/histories from the conftest
factories; CLI-level tests write a real cache into ``tmp_path`` and exercise the
exit codes. Never touches the real account.

Output is asserted to be ASCII-direction-only (``+`` / ``-`` / ``=``, never raw
arrows) so it cannot raise ``UnicodeEncodeError`` on a cp1252 console.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics import sessiondiff
from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.cli import main
from hevy_brain.models import build_records
from hevy_brain.store.cache import CacheStore


def _cache(tmp_path: Path, workouts: dict[str, dict]) -> None:
    """Persist a raw-workout cache into ``tmp_path/data`` for the CLI to read."""
    store = CacheStore(tmp_path / "data")
    store.workouts = workouts
    store.save()


def _two_sessions() -> dict[str, dict]:
    """Two bench+row sessions a week apart, bench progressing 60x8 -> 65x8.

    The earlier session has a warm-up before the working bench set, so the
    heaviest-working-set scan must skip it. Volume rises, duration shortens.
    """
    w1 = make_workout(
        "w1",
        "Push Day",
        start="2026-05-25T17:00:00+00:00",
        end="2026-05-25T18:10:00+00:00",  # 70 min
        exercises=[
            make_exercise(
                "Bench Press (Barbell)",
                "T-BENCH",
                sets=[
                    make_set(40, 10, type="warmup"),  # must be ignored
                    make_set(60, 8),
                    make_set(60, 8),
                ],
            ),
            make_exercise("Lateral Raise (Dumbbell)", "T-LAT", [make_set(10, 12)], 1),
        ],
    )
    w2 = make_workout(
        "w2",
        "Push Day",
        start="2026-06-01T17:00:00+00:00",
        end="2026-06-01T18:00:00+00:00",  # 60 min
        exercises=[
            make_exercise(
                "Bench Press (Barbell)",
                "T-BENCH",
                sets=[make_set(65, 8), make_set(65, 8)],
            ),
            make_exercise("Triceps Pushdown (Cable)", "T-TRI", [make_set(30, 12)], 1),
        ],
    )
    return {w["id"]: w for w in (w1, w2)}


# --- overall (whole-workout) diff --------------------------------------------


def test_overall_diff_headline_deltas() -> None:
    records = build_records(_two_sessions())
    diff = sessiondiff.overall_diff(records[-2], records[-1])

    # Workout volume includes warm-ups (matches the Dashboard's definition):
    # w1 = 40*10 + 60*8 + 60*8 + 10*12 = 1480; w2 = 65*8 + 65*8 + 30*12 = 1400.
    assert diff["prior_volume_kg"] == 1480
    assert diff["latest_volume_kg"] == 1400
    assert diff["volume_delta_kg"] == -80
    # Duration 70 -> 60 min.
    assert diff["duration_delta_min"] == -10
    # Same exercise count (2 each).
    assert diff["exercise_count_delta"] == 0


def test_overall_diff_shared_exercise_top_set_change() -> None:
    records = build_records(_two_sessions())
    diff = sessiondiff.overall_diff(records[-2], records[-1])

    shared = {e["exercise"]: e for e in diff["exercises"]}
    assert list(shared) == ["Bench Press (Barbell)"]  # only exercise in both
    bench = shared["Bench Press (Barbell)"]
    # Heaviest WORKING set each side: 60x8 (warm-up 40 skipped) -> 65x8.
    assert bench["prior_set"]["weight_kg"] == 60
    assert bench["latest_set"]["weight_kg"] == 65
    assert bench["weight_delta_kg"] == 5


def test_overall_diff_added_and_dropped() -> None:
    records = build_records(_two_sessions())
    diff = sessiondiff.overall_diff(records[-2], records[-1])
    assert diff["added"] == ["Triceps Pushdown (Cable)"]
    assert diff["dropped"] == ["Lateral Raise (Dumbbell)"]


def test_render_overall_is_ascii_direction_only() -> None:
    records = build_records(_two_sessions())
    lines = sessiondiff.render_overall(
        sessiondiff.overall_diff(records[-2], records[-1])
    )
    text = "\n".join(lines)
    # Cannot raise on a cp1252 console, and is genuinely ASCII-only.
    text.encode("ascii")
    text.encode("cp1252")
    for arrow in ("↑", "↓"):  # raw up/down arrows
        assert arrow not in text
    assert "-80 kg" in text  # signed volume delta (warm-up-inclusive)
    assert "-10 min" in text  # signed duration delta


def test_render_overall_absent_top_set_is_ascii() -> None:
    """A shared exercise that is all warm-up on the later side has no working
    set, so its top-set label renders the ASCII '(none)' placeholder. The whole
    rendered diff must stay ASCII-only (the absent-set path is the one that used
    to emit a raw em-dash)."""
    w1 = make_workout(
        "w1",
        "Push Day",
        start="2026-05-25T17:00:00+00:00",
        end="2026-05-25T18:00:00+00:00",
        exercises=[
            make_exercise("Bench Press (Barbell)", "T-BENCH", [make_set(60, 8)]),
        ],
    )
    w2 = make_workout(
        "w2",
        "Push Day",
        start="2026-06-01T17:00:00+00:00",
        end="2026-06-01T18:00:00+00:00",
        exercises=[
            # Only a warm-up this session -> no working set -> absent top set.
            make_exercise(
                "Bench Press (Barbell)",
                "T-BENCH",
                [make_set(40, 10, type="warmup")],
            ),
        ],
    )
    records = build_records({"w1": w1, "w2": w2})
    diff = sessiondiff.overall_diff(records[-2], records[-1])
    bench = {e["exercise"]: e for e in diff["exercises"]}["Bench Press (Barbell)"]
    assert bench["latest_set"] is None  # all-warm-up side has no working set

    text = "\n".join(sessiondiff.render_overall(diff))
    assert "(none)" in text  # the absent top set renders the ASCII placeholder
    text.encode("ascii")  # ASCII-only contract on the absent-set path
    assert "—" not in text  # never a raw em-dash


def test_heaviest_working_set_ignores_warmups_and_handles_bodyweight() -> None:
    # All warm-ups -> falls through to the heaviest non-warm-up (none) = None.
    only_warmups = make_exercise(sets=[make_set(40, 10, type="warmup")])
    assert sessiondiff._heaviest_working_set(only_warmups) is None

    # Bodyweight-only (weight None): eligible, returned as the top set.
    bodyweight = make_exercise(sets=[make_set(weight_kg=None, reps=12)])
    top = sessiondiff._heaviest_working_set(bodyweight)
    assert top is not None
    assert top["weight_kg"] is None


# --- per-exercise diff -------------------------------------------------------


def test_exercise_diff_deltas() -> None:
    records = build_records(_two_sessions())
    histories = exercise_histories(records)
    diff = sessiondiff.exercise_diff(histories["Bench Press (Barbell)"])

    assert diff["prior_set"]["weight_kg"] == 60
    assert diff["latest_set"]["weight_kg"] == 65
    assert diff["top_weight_delta_kg"] == 5
    # est 1RM: 60*(1+8/30)=76.0 -> 65*(1+8/30)=82.33...; delta ~6.33.
    assert round(diff["prior_e1rm_kg"], 2) == 76.0
    assert round(diff["latest_e1rm_kg"], 2) == 82.33
    assert round(diff["e1rm_delta_kg"], 2) == 6.33
    # Per-exercise session volume + reps include the warm-up (as elsewhere in
    # the app): w1 = 40*10 + 60*8 + 60*8 = 1360 kg / 26 reps; w2 = 1040 kg / 16.
    assert diff["volume_delta_kg"] == -320
    assert diff["reps_delta"] == -10


def test_exercise_diff_sorts_by_date_not_input_order() -> None:
    """Sessions are sorted by date here, so unordered history still diffs the
    two most recent correctly."""
    records = build_records(_two_sessions())
    history = exercise_histories(records)["Bench Press (Barbell)"]
    history["sessions"].reverse()  # scramble order
    diff = sessiondiff.exercise_diff(history)
    assert diff["prior_date"].isoformat() == "2026-05-25"
    assert diff["latest_date"].isoformat() == "2026-06-01"


def test_render_exercise_is_ascii_direction_only() -> None:
    records = build_records(_two_sessions())
    history = exercise_histories(records)["Bench Press (Barbell)"]
    text = "\n".join(sessiondiff.render_exercise(sessiondiff.exercise_diff(history)))
    text.encode("cp1252")  # must not raise
    assert "↑" not in text
    assert "↓" not in text
    assert "+5 kg" in text  # top-set delta


def test_exercise_diff_bodyweight_session_degrades_honestly() -> None:
    """A bodyweight session stores best_set=None and best_e1rm_kg=0: the per-
    exercise diff shows no weighted top set ('(none)') and 0 est-1RM, but the
    reps delta still carries the signal: no crash, ASCII-only output."""
    pull = "Pull Up"
    w1 = make_workout(
        "w1",
        start="2026-05-25T17:00:00+00:00",
        end="2026-05-25T18:00:00+00:00",
        exercises=[make_exercise(pull, "T-PULL", [make_set(weight_kg=None, reps=10)])],
    )
    w2 = make_workout(
        "w2",
        start="2026-06-01T17:00:00+00:00",
        end="2026-06-01T18:00:00+00:00",
        exercises=[make_exercise(pull, "T-PULL", [make_set(weight_kg=None, reps=12)])],
    )
    history = exercise_histories(build_records({"w1": w1, "w2": w2}))[pull]
    diff = sessiondiff.exercise_diff(history)
    assert diff["prior_set"] is None  # no e1rm-positive set -> no stored top set
    assert diff["prior_e1rm_kg"] == 0.0  # bodyweight has no est-1RM
    assert diff["reps_delta"] == 2
    text = "\n".join(sessiondiff.render_exercise(diff))
    # Absent top set on both sides renders the ASCII '(none)' placeholder.
    assert "(none)" in text
    text.encode("ascii")  # ASCII-only contract: must not raise (stricter)
    text.encode("cp1252")  # and trivially cp1252-safe
    assert "10 -> 12" in text  # reps still report
    # The heaviest-working-set helper still labels a raw bodyweight set dict
    # (the overall path scans sets directly, where weight_kg=None is present).
    assert sessiondiff._set_label(make_set(weight_kg=None, reps=12)) == "bodyweight x 12"


# --- CLI-level exit codes ----------------------------------------------------


def test_cli_diff_overall_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _cache(tmp_path, _two_sessions())
    rc = main(["diff"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Last two sessions" in out
    assert "Bench Press (Barbell)" in out


def test_cli_diff_exercise_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _cache(tmp_path, _two_sessions())
    rc = main(["diff", "bench"])  # unique substring resolves
    assert rc == 0
    out = capsys.readouterr().out
    assert "Bench Press (Barbell)" in out
    assert "est 1RM" in out


def test_cli_diff_single_session_is_honest_exit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    # Only one workout in the cache.
    _cache(tmp_path, {"w1": make_workout("w1")})
    rc = main(["diff"])
    assert rc == 0  # honest degrade, not an error
    assert "at least two sessions" in capsys.readouterr().out


def test_cli_diff_single_session_for_exercise_exit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _cache(tmp_path, {"w1": make_workout("w1")})  # Bench Press once only
    rc = main(["diff", "bench"])
    assert rc == 0
    assert "at least two sessions" in capsys.readouterr().out


def test_cli_diff_ambiguous_name_exit_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    # Two exercises both containing "press" -> ambiguous.
    w1 = make_workout(
        "w1",
        start="2026-05-25T17:00:00+00:00",
        end="2026-05-25T18:00:00+00:00",
        exercises=[
            make_exercise("Bench Press (Barbell)", "T-BENCH", [make_set(60, 8)]),
            make_exercise("Overhead Press (Barbell)", "T-OHP", [make_set(40, 8)], 1),
        ],
    )
    w2 = make_workout(
        "w2",
        start="2026-06-01T17:00:00+00:00",
        end="2026-06-01T18:00:00+00:00",
        exercises=[
            make_exercise("Bench Press (Barbell)", "T-BENCH", [make_set(62, 8)]),
            make_exercise("Overhead Press (Barbell)", "T-OHP", [make_set(42, 8)], 1),
        ],
    )
    _cache(tmp_path, {"w1": w1, "w2": w2})
    rc = main(["diff", "press"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "ambiguous" in err
    assert "Bench Press (Barbell)" in err
    assert "Overhead Press (Barbell)" in err


def test_cli_diff_unknown_name_exit_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _cache(tmp_path, _two_sessions())
    rc = main(["diff", "deadlift"])
    assert rc == 1
    assert "No exercise matching" in capsys.readouterr().err


def test_cli_diff_empty_cache_exit_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _cache(tmp_path, {})
    rc = main(["diff"])
    assert rc == 1
    assert "Cache is empty" in capsys.readouterr().err
