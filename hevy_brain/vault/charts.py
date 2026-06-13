"""Mermaid xychart-beta renderers for progress trends.

Zero-dependency: Obsidian renders ```mermaid blocks natively (xychart-beta is
Mermaid >= v10.6.0; Obsidian ships 11.x). Both progress charts are **bar**
charts on purpose: Mermaid line series can render invisibly under some Obsidian
themes (stroke-width resolves to 0), and bars never imply false continuity
between irregularly spaced sessions.

Labels are ISO-native to match the rest of the vault (ISO weeks "W23" for the
weekly trend; "mm-dd" dates for the per-exercise trend, widening to "yy-mm-dd"
only when the window spans more than one calendar year). Output is fully
deterministic so a rebuild over unchanged data stays byte-identical.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from ..analytics import stats

_MIN_POINTS = 2


def _clean(text: str) -> str:
    """Strip characters that would break a single-line Mermaid directive.

    Removes double-quotes and square brackets (grammar), and commas (the
    x-axis list delimiter), then collapses any whitespace/newlines to a single
    space. Applied to the title, the y-axis label, and every x-axis label so
    none can corrupt the block — defensive even though today's labels are
    machine-generated ISO tokens and the titles are constants.
    """
    cleaned = (
        str(text)
        .replace('"', "")
        .replace("[", "")
        .replace("]", "")
        .replace(",", " ")
    )
    return " ".join(cleaned.split())


def _fmt(value: float) -> str:
    """Locale-independent: integer when whole, else 1 dp. Normalises -0.0."""
    if value == 0:
        value = 0.0
    return f"{value:.0f}" if value == int(value) else f"{value:.1f}"


def _nice_ceiling(value: float) -> int:
    """Round up to 1-2 significant figures (8433 -> 9000, 92 -> 100)."""
    if value <= 0:
        return 1
    base = 10 ** math.floor(math.log10(value))
    return int(math.ceil(value / base) * base)


def _floor_to(value: float, step: int) -> int:
    return int(math.floor(value / step) * step)


def _ceil_to(value: float, step: int) -> int:
    return int(math.ceil(value / step) * step)


def mermaid_xychart(
    title: str,
    labels: list[str],
    values: list[float],
    *,
    y_label: str,
    zero_baseline: bool = False,
) -> str | None:
    """Render a Mermaid xychart-beta bar chart, or None if not worth drawing.

    Drops non-finite points (a single NaN must never abort the build); returns
    None for fewer than two finite points or an all-zero series. The y-axis is
    0-based when ``zero_baseline`` (volume), else a padded nearest-5 band so a
    small strength trend stays visible.
    """
    points = [
        (lbl, float(v))
        for lbl, v in zip(labels, values, strict=False)
        if isinstance(v, (int, float))
        and not isinstance(v, bool)
        and math.isfinite(v)
    ]
    if len(points) < _MIN_POINTS or not any(v != 0 for _, v in points):
        return None

    vals = [v for _, v in points]
    if zero_baseline:
        lo, hi = 0, _nice_ceiling(max(vals))
    else:
        lo = max(0, _floor_to(min(vals) - 2.5, 5))
        hi = _ceil_to(max(vals) + 2.5, 5)
    if hi <= lo:
        hi = lo + 1

    label_list = ", ".join(f'"{_clean(lbl)}"' for lbl, _ in points)
    value_list = ", ".join(_fmt(v) for _, v in points)
    return (
        "```mermaid\n"
        "xychart-beta\n"
        f'    title "{_clean(title)}"\n'
        f"    x-axis [{label_list}]\n"
        f'    y-axis "{_clean(y_label)}" {lo} --> {hi}\n'
        f"    bar [{value_list}]\n"
        "```"
    )


def chart_section(
    heading: str, chart: str | None, caption: str | None = None
) -> list[str]:
    """Heading + chart (+ optional caption), or [] when there is no chart.

    Keeps every call site from leaving an orphan heading above a missing chart.
    """
    if not chart:
        return []
    lines = [f"\n## {heading}", "\n" + chart]
    if caption:
        lines.append(f"\n*{caption}*")
    return lines


def weekly_volume_points(
    records: list[dict[str, Any]], weeks: int, today: date
) -> tuple[list[str], list[float]]:
    """Contiguous last-``weeks`` ISO-week volume buckets ending at today's week.

    Untrained weeks are 0 so a training gap reads as elapsed time, not
    compressed bars. Labels are ISO week numbers ("W23"), the vault's native
    weekly unit (reviews are titled YYYY-Www).
    """
    series = stats.weekly_series(records)
    current = stats.week_start(today)
    labels: list[str] = []
    values: list[float] = []
    for offset in range(weeks - 1, -1, -1):
        bucket = current - timedelta(weeks=offset)
        labels.append(f"W{bucket.isocalendar().week:02d}")
        values.append(round(series.get(bucket, {}).get("volume_kg", 0.0)))
    return labels, values


def weekly_volume_chart(
    records: list[dict[str, Any]], weeks: int, today: date
) -> str | None:
    """Weekly-volume bar chart for the Dashboard."""
    if weeks <= 0:
        return None
    labels, values = weekly_volume_points(records, weeks, today)
    return mermaid_xychart(
        "Weekly volume (kg)",
        labels,
        values,
        y_label="Volume (kg)",
        zero_baseline=True,
    )


def e1rm_points(
    history: dict[str, Any], max_points: int
) -> tuple[list[str], list[float]]:
    """Estimated-1RM series for one exercise: loaded sessions only.

    Sessions with best_e1rm_kg == 0 (bodyweight/cardio) are excluded, so a
    pure-bodyweight exercise yields no chart. Labels are "mm-dd", widening to
    "yy-mm-dd" only when the kept sessions span more than one calendar year.
    """
    sessions = [s for s in history["sessions"] if s.get("best_e1rm_kg", 0) > 0]
    sessions = sessions[-max_points:] if max_points > 0 else []
    if not sessions:
        return [], []
    multiyear = sessions[0]["date"].year != sessions[-1]["date"].year
    fmt = "%y-%m-%d" if multiyear else "%m-%d"
    labels = [s["date"].strftime(fmt) for s in sessions]
    values = [round(s["best_e1rm_kg"], 1) for s in sessions]
    return labels, values


def e1rm_chart(history: dict[str, Any], max_points: int) -> str | None:
    """Estimated-1RM trend bar chart for one exercise note."""
    if max_points <= 0:
        return None
    labels, values = e1rm_points(history, max_points)
    return mermaid_xychart(
        "est. 1RM trend (kg)", labels, values, y_label="est. 1RM (kg)"
    )
