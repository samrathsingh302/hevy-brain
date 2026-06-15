"""Tests for per-lift progression targets (B1)."""

from __future__ import annotations

from pathlib import Path

from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics.progression import next_target
from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.config import Config
from hevy_brain.models import build_records
from hevy_brain.vault.exercises import render_exercise_note

_DATES = [
    "2026-05-25",
    "2026-06-01",
    "2026-06-08",
    "2026-06-15",
]


def _cfg(tmp_path: Path | None = None, **overrides: object) -> Config:
    base = tmp_path or Path()
    return Config(base_dir=base, vault_path=base / "vault", **overrides)  # type: ignore[arg-type]


def _history(sets_per_session: list[list[tuple[float | None, int | None]]]) -> dict:
    """Build one exercise's history from a list of per-session set tuples.

    Each session is a list of (weight_kg, reps) sets; sessions are dated in
    ascending order so the last list is the most-recent session.
    """
    raw = {}
    for i, session_sets in enumerate(sets_per_session):
        day = _DATES[i]
        raw[f"w{i}"] = make_workout(
            f"w{i}",
            "Push Day",
            start=f"{day}T17:00:00+00:00",
            end=f"{day}T18:00:00+00:00",
            exercises=[
                make_exercise(
                    "Bench Press (Barbell)",
                    "T-BENCH",
                    [make_set(w, r) for (w, r) in session_sets],
                )
            ],
        )
    histories = exercise_histories(build_records(raw))
    return histories["Bench Press (Barbell)"]


def test_rep_add_when_below_top_of_range() -> None:
    # Three sessions, last top set 60 kg x 8 -> add a rep.
    history = _history([[(60, 8)], [(60, 8)], [(60, 8)]])
    target = next_target(history, _cfg())
    assert target is not None
    assert target["current_weight_kg"] == 60.0
    assert target["current_reps"] == 8
    assert target["target_weight_kg"] == 60.0
    assert target["target_reps"] == 9
    assert "60 kg × 8" in target["note"]
    assert "60 kg × 9" in target["note"]


def test_load_add_and_reset_at_top_of_range() -> None:
    # Last top set 20 kg x 12 (== rep_high) -> +2.5 kg, reset to rep_low (8).
    # Epley(22.5, 8)=28.5 > Epley(20, 12)=28.0, so the guard does not fire.
    history = _history([[(20, 12)], [(20, 12)], [(20, 12)]])
    target = next_target(history, _cfg())
    assert target is not None
    assert target["target_weight_kg"] == 22.5
    assert target["target_reps"] == 8


def test_no_regression_guard_falls_back_to_rep_add() -> None:
    # 60 kg x 12: a +2.5 kg / reset-to-8 target estimates a LOWER 1RM
    # (Epley(62.5, 8)=79.2 <= Epley(60, 12)=84.0), so it falls back to 60 x 13.
    history = _history([[(60, 12)], [(60, 12)], [(60, 12)]])
    target = next_target(history, _cfg())
    assert target is not None
    assert target["target_weight_kg"] == 60.0
    assert target["target_reps"] == 13


def test_bodyweight_only_lift_returns_none() -> None:
    # Pull-ups etc. carry weight_kg=None -> no load to progress.
    history = _history([[(None, 10)], [(None, 10)], [(None, 10)]])
    assert next_target(history, _cfg()) is None


def test_zero_weight_lift_returns_none() -> None:
    history = _history([[(0, 10)], [(0, 10)], [(0, 10)]])
    assert next_target(history, _cfg()) is None


def test_thin_history_returns_none() -> None:
    # Two sessions < min_sessions (3) -> not enough to suggest a target.
    history = _history([[(60, 8)], [(60, 8)]])
    assert next_target(history, _cfg()) is None


def test_disabled_returns_none() -> None:
    history = _history([[(60, 8)], [(60, 8)], [(60, 8)]])
    assert next_target(history, _cfg(progression_enabled=False)) is None


def test_uses_most_recent_session_not_best_ever() -> None:
    # Heavy first session, lighter recent one -> the target tracks the most
    # recent top set (62 -> 63 reps), not the all-time best (100).
    history = _history([[(100, 5)], [(80, 6)], [(62, 8)]])
    target = next_target(history, _cfg())
    assert target is not None
    assert target["current_weight_kg"] == 62.0
    assert target["current_reps"] == 8
    assert target["target_reps"] == 9


def test_basis_is_top_e1rm_set_in_recent_session() -> None:
    # Within the most recent session, the basis is the highest-e1RM set:
    # 70 x 5 (e1RM 81.7) beats 60 x 8 (e1RM 76), so basis = (70, 5) -> (70, 6).
    history = _history([[(60, 8)], [(60, 8)], [(60, 8), (70, 5)]])
    target = next_target(history, _cfg())
    assert target is not None
    assert target["current_weight_kg"] == 70.0
    assert target["current_reps"] == 5
    assert target["target_reps"] == 6


def test_latest_same_day_session_wins() -> None:
    # Two workouts on the SAME calendar day: a morning session (50 kg x 8) and
    # a later evening session (70 kg x 5). Sessions store only `date`, so both
    # share the equal-max date; the genuinely-latest (last in list) must be the
    # basis -> target tracks the evening 70 x 5, not the morning 50 x 8.
    same_day = "2026-06-15"
    morning = make_workout(
        "w-am",
        "Push Day",
        start=f"{same_day}T08:00:00+00:00",
        end=f"{same_day}T09:00:00+00:00",
        exercises=[
            make_exercise("Bench Press (Barbell)", "T-BENCH", [make_set(50, 8)])
        ],
    )
    evening = make_workout(
        "w-pm",
        "Push Day",
        start=f"{same_day}T18:00:00+00:00",
        end=f"{same_day}T19:00:00+00:00",
        exercises=[
            make_exercise("Bench Press (Barbell)", "T-BENCH", [make_set(70, 5)])
        ],
    )
    # Two earlier days satisfy progression_min_sessions (3) before the same-day pair.
    earlier = {
        f"w{i}": make_workout(
            f"w{i}",
            "Push Day",
            start=f"{_DATES[i]}T17:00:00+00:00",
            end=f"{_DATES[i]}T18:00:00+00:00",
            exercises=[
                make_exercise("Bench Press (Barbell)", "T-BENCH", [make_set(60, 8)])
            ],
        )
        for i in range(2)
    }
    raw = {**earlier, "w-am": morning, "w-pm": evening}
    history = exercise_histories(build_records(raw))["Bench Press (Barbell)"]

    target = next_target(history, _cfg())
    assert target is not None
    assert target["current_weight_kg"] == 70.0
    assert target["current_reps"] == 5
    assert target["target_reps"] == 6
    assert "70 kg × 5" in target["note"]


def test_min_sessions_override() -> None:
    # With min_sessions=1, a single session is enough.
    history = _history([[(60, 8)]])
    target = next_target(history, _cfg(progression_min_sessions=1))
    assert target is not None
    assert target["target_reps"] == 9


def test_rendered_section_present_and_omitted() -> None:
    history = _history([[(60, 8)], [(60, 8)], [(60, 8)]])
    note = render_exercise_note(history, {}, 0, _cfg())
    assert "Next session target" in note
    assert "60 kg × 9" in note

    # No config -> no section, no orphan heading.
    note_none = render_exercise_note(history, {}, 0, None)
    assert "Next session target" not in note_none

    # Disabled -> no section.
    note_off = render_exercise_note(history, {}, 0, _cfg(progression_enabled=False))
    assert "Next session target" not in note_off

    # Bodyweight-only -> no section.
    bw = _history([[(None, 10)], [(None, 10)], [(None, 10)]])
    note_bw = render_exercise_note(bw, {}, 0, _cfg())
    assert "Next session target" not in note_bw


def test_rendered_section_is_idempotent() -> None:
    history = _history([[(60, 8)], [(60, 8)], [(60, 8)]])
    cfg = _cfg()
    first = render_exercise_note(history, {}, 0, cfg)
    second = render_exercise_note(history, {}, 0, cfg)
    assert first == second
