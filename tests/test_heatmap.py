"""Tests for the consistency-heatmap renderer (working-set count per day)."""

from __future__ import annotations

from datetime import date

from conftest import make_exercise, make_set, make_workout

from hevy_brain.models import build_records
from hevy_brain.vault import heatmap
from hevy_brain.vault.dashboards import _consistency_heatmap_lines, render_dashboard

# A Wednesday: stats.week_start(TODAY) == 2026-06-08 (Mon of that ISO week).
TODAY = date(2026, 6, 10)


def _workout(day: str, working: int = 1, *, warmups: int = 0) -> dict:
    """One workout on ``day`` with ``working`` working sets + ``warmups`` warm-ups."""
    sets = [make_set(60, 8) for _ in range(working)]
    sets += [make_set(20, 12, type="warmup") for _ in range(warmups)]
    return make_workout(
        workout_id=f"w-{day}-{working}-{warmups}",
        start=f"{day}T17:00:00+00:00",
        end=f"{day}T18:00:00+00:00",
        exercises=[make_exercise(sets=sets)],
    )


def _block(workouts: list[dict], *, weeks: int = 26, today: date = TODAY):
    return heatmap.heatmap_block(
        build_records({w["id"]: w for w in workouts}), weeks, today
    )


# --- the pure renderer -------------------------------------------------------


def test_dense_history_has_seven_day_rows_and_legend() -> None:
    # Train every Monday for the last 6 weeks within a 26-week window.
    mondays = ["2026-05-04", "2026-05-11", "2026-05-18", "2026-05-25", "2026-06-01"]
    block = _block([_workout(d, working=5) for d in mondays])

    assert block is not None
    text = "\n".join(block)
    assert "## Consistency (last 26 weeks)" in text
    assert "```text" in text
    # 7 day-rows, one per weekday label, Mon->Sun.
    for label in ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"):
        assert any(line.startswith(label + " ") for line in block)
    assert "Legend:" in text
    assert "working sets/day" in text
    # The Monday rows carry a shade; an untrained weekday stays blank.
    mo_row = next(line for line in block if line.startswith("Mo "))
    su_row = next(line for line in block if line.startswith("Su "))
    assert any(ch in mo_row for ch in "·░▒▓")
    assert set(su_row.removeprefix("Su ")) == {" "}


def test_warmups_excluded_from_the_count() -> None:
    # Two days: one with 4 working sets, one that is ALL warm-ups (0 working).
    block = _block(
        [
            _workout("2026-05-25", working=4),
            _workout("2026-06-01", working=0, warmups=6),
            _workout("2026-05-18", working=2),
        ]
    )
    # The all-warmup day contributes nothing, but two real weeks remain.
    assert block is not None
    # 4 working sets is the window max -> its day is the busiest glyph '▓'.
    grid = [
        line for line in block if line[:2] in {"Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"}
    ]
    assert any("▓" in line for line in grid)


def test_sparse_lapsed_history_mostly_empty_no_crash() -> None:
    # Two trained weeks far in the past; the recent weeks (the lapse) are blank.
    block = _block(
        [_workout("2026-01-12", working=3), _workout("2026-01-19", working=2)],
        today=date(2026, 6, 10),
    )
    assert block is not None
    grid = "".join(
        line.split(" ", 1)[1]
        for line in block
        if line[:2] in {"Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"}
    )
    # Overwhelmingly rest: only two trained days in a 26-week (182-day) window.
    shaded = sum(grid.count(ch) for ch in "·░▒▓")
    assert shaded == 2
    assert grid.count(" ") >= 100


def test_no_section_when_window_has_no_working_sets() -> None:
    # All training is OLDER than the 26-week window -> nothing in range -> omit.
    block = _block(
        [_workout("2025-01-06", working=4), _workout("2025-01-13", working=4)],
        today=date(2026, 6, 10),
    )
    assert block is None  # max_count would be 0 -> div-by-zero guard fires as omit


def test_no_section_for_all_warmup_window() -> None:
    # Real workouts in-window but every set is a warm-up -> 0 working sets -> omit.
    block = _block(
        [
            _workout("2026-05-25", working=0, warmups=5),
            _workout("2026-06-01", working=0, warmups=5),
        ]
    )
    assert block is None


def test_no_section_for_fewer_than_two_trained_weeks() -> None:
    # Two sessions, but both in the SAME ISO week -> <2 distinct weeks -> omit.
    block = _block(
        [_workout("2026-06-01", working=4), _workout("2026-06-03", working=4)]
    )
    assert block is None


def test_no_section_for_non_positive_weeks() -> None:
    assert _block([_workout("2026-06-01"), _workout("2026-05-25")], weeks=0) is None


def test_quartile_glyph_mapping_at_band_edges() -> None:
    # max_count = 8 -> edges at 2,4,6,8: counts 2->'·',4->'░',6->'▒',8->'▓'.
    assert heatmap._glyph(0, 8) == " "
    assert heatmap._glyph(1, 8) == "·"
    assert heatmap._glyph(2, 8) == "·"
    assert heatmap._glyph(3, 8) == "░"
    assert heatmap._glyph(4, 8) == "░"
    assert heatmap._glyph(5, 8) == "▒"
    assert heatmap._glyph(6, 8) == "▒"
    assert heatmap._glyph(7, 8) == "▓"
    assert heatmap._glyph(8, 8) == "▓"


def test_render_is_byte_identical_when_repeated() -> None:
    workouts = [
        _workout(d, working=i + 1)
        for i, d in enumerate(["2026-05-04", "2026-05-11", "2026-05-18", "2026-06-01"])
    ]
    first = _block(workouts)
    second = _block(workouts)
    assert first is not None
    assert first == second
    assert "\n".join(first) == "\n".join(second)


def test_grid_width_matches_weeks() -> None:
    block = _block(
        [_workout("2026-05-25", working=2), _workout("2026-06-01", working=4)],
        weeks=26,
    )
    assert block is not None
    mo_row = next(line for line in block if line.startswith("Mo "))
    assert len(mo_row.removeprefix("Mo ")) == 26  # one column per week


# --- the dashboard helper (enabled gate + omission) --------------------------


def test_helper_omits_when_disabled() -> None:
    records = build_records(
        {w["id"]: w for w in [_workout("2026-05-25", 4), _workout("2026-06-01", 4)]}
    )
    assert _consistency_heatmap_lines(records, TODAY, enabled=False, weeks=26) == []
    # Enabled, with two trained weeks, renders something.
    assert _consistency_heatmap_lines(records, TODAY, enabled=True, weeks=26) != []


def test_dashboard_includes_heatmap_when_enabled() -> None:
    records = build_records(
        {
            w["id"]: w
            for w in [
                _workout("2026-05-25", 5),
                _workout("2026-06-01", 3),
                _workout("2026-05-18", 2),
            ]
        }
    )
    out = render_dashboard(
        records, {}, {}, {}, TODAY, heatmap_enabled=True, heatmap_weeks=26
    )
    assert "## Consistency (last 26 weeks)" in out
    assert "```text" in out
    # Default (disabled) keeps it off.
    off = render_dashboard(records, {}, {}, {}, TODAY)
    assert "## Consistency" not in off
