"""GitHub-style training-consistency heatmap for the Dashboard.

Renders a fenced monospace grid of the last ``weeks`` ISO weeks: 7 day-rows
(Mon->Sun) x ``weeks`` columns, one cell per calendar day. The cell shade is the
**working-set count** that day (non-warmup sets logged) mapped to a glyph, so a
bodyweight day (volume 0 but real training) still shows, and a lapse reads
honestly as blank space.

Fully deterministic: the only date-derived text is the window's date range,
derived from ``today``, so a rebuild over unchanged data with the same ``today``
stays byte-identical (idempotency fence).
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from ..analytics import stats

# Band 0 (no working sets) is a space so rest days / lapses read as blank; the
# four positive bands are equal-width quartiles of (0, max_count], busiest last.
_REST = " "
_SHADES = ("·", "░", "▒", "▓")  # · ░ ▒ ▓
_DAY_LABELS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
_MIN_TRAINED_WEEKS = 2


def _working_sets_by_day(records: list[dict[str, Any]]) -> dict[date, int]:
    """Map each calendar day to its count of non-warmup (working) sets."""
    counts: dict[date, int] = {}
    for record in records:
        day = record["start_time"].date()
        working = sum(
            1
            for exercise in record["exercises"]
            for s in exercise["sets"]
            if s.get("type") != "warmup"
        )
        if working:
            counts[day] = counts.get(day, 0) + working
    return counts


def _glyph(count: int, max_count: int) -> str:
    """Map a day's working-set count to its heatmap glyph.

    ``count == 0`` is rest (a space). A positive count falls into one of four
    equal-width quartiles of ``(0, max_count]``: ``(0,1/4]`` -> '·' ... up to
    ``(3/4,1]`` -> '▓'. ``max_count`` is guaranteed > 0 by the caller (the whole
    section is omitted when it is 0), so this never divides by zero.
    """
    if count <= 0:
        return _REST
    band = math.ceil(count / max_count * 4)
    band = max(1, min(4, band))
    return _SHADES[band - 1]


def heatmap_block(
    records: list[dict[str, Any]], weeks: int, today: date
) -> list[str] | None:
    """Render the consistency heatmap as Markdown lines, or None to omit it.

    Returns None (no orphan heading) when ``weeks`` is non-positive, when no
    working sets fall in the window (``max_count == 0`` -> guards the quartile
    division), or when fewer than two distinct weeks were trained in the window.
    The grid is a ```text fence so glyph columns stay monospaced in Obsidian.
    """
    if weeks <= 0:
        return None

    last_week_start = stats.week_start(today)
    first_week_start = last_week_start - timedelta(weeks=weeks - 1)
    window_end = last_week_start + timedelta(days=7)  # exclusive (Sun inclusive)

    counts = _working_sets_by_day(records)
    in_window = {
        day: n for day, n in counts.items() if first_week_start <= day < window_end
    }
    if not in_window:
        return None
    max_count = max(in_window.values())
    if max_count <= 0:  # defensive: _working_sets_by_day never stores a 0
        return None

    trained_weeks = {stats.week_start(day) for day in in_window}
    if len(trained_weeks) < _MIN_TRAINED_WEEKS:
        return None

    rows: list[str] = []
    for weekday in range(7):  # 0=Mon .. 6=Sun
        cells = [
            _glyph(
                in_window.get(
                    first_week_start + timedelta(weeks=col, days=weekday), 0
                ),
                max_count,
            )
            for col in range(weeks)
        ]
        rows.append(f"{_DAY_LABELS[weekday]} {''.join(cells)}")

    last_day = window_end - timedelta(days=1)
    legend = (
        f"Legend: '{_REST}'=rest "
        f"'{_SHADES[0]}'<'{_SHADES[1]}'<'{_SHADES[2]}'<'{_SHADES[3]}' busier "
        "(working sets/day)"
    )
    return [
        f"\n## Consistency (last {weeks} weeks)",
        f"\n_{first_week_start.isoformat()} to {last_day.isoformat()}_",
        "\n```text",
        *rows,
        "```",
        f"\n{legend}",
    ]
