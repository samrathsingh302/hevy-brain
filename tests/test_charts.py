"""Tests for the Mermaid xychart progress-chart renderer and point builders."""

from __future__ import annotations

import re
from datetime import date, timedelta

from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics import stats
from hevy_brain.analytics.prs import epley_1rm, exercise_histories
from hevy_brain.models import build_records
from hevy_brain.vault import charts

TODAY = date(2026, 6, 10)


# --- renderer ----------------------------------------------------------------


def test_returns_none_for_fewer_than_two_points() -> None:
    assert charts.mermaid_xychart("t", ["a"], [1], y_label="y") is None
    assert charts.mermaid_xychart("t", [], [], y_label="y") is None


def test_returns_none_for_all_zero_series() -> None:
    assert (
        charts.mermaid_xychart("t", ["a", "b"], [0, 0], y_label="y", zero_baseline=True)
        is None
    )


def test_drops_non_finite_points_and_guards_the_remainder() -> None:
    # NaN must never reach int() and abort the build — it is dropped.
    out = charts.mermaid_xychart(
        "t", ["a", "b", "c"], [10, float("nan"), 20], y_label="y", zero_baseline=True
    )
    assert out is not None
    assert "nan" not in out.lower()
    assert "bar [10, 20]" in out
    # the dropped value's label is dropped too (pairs stay aligned)
    assert 'x-axis ["a", "c"]' in out
    # Only one finite point left -> not worth a chart.
    assert (
        charts.mermaid_xychart("t", ["a", "b"], [float("inf"), 5], y_label="y") is None
    )


def test_structure_and_zero_baseline() -> None:
    out = charts.mermaid_xychart(
        "Weekly volume (kg)",
        ["W21", "W22"],
        [1000, 2000],
        y_label="Volume (kg)",
        zero_baseline=True,
    )
    assert out.startswith("```mermaid\nxychart-beta\n")
    assert out.endswith("```")
    assert 'x-axis ["W21", "W22"]' in out
    assert 'y-axis "Volume (kg)" 0 --> 2000' in out
    assert "bar [1000, 2000]" in out


def test_nonzero_baseline_is_a_padded_nearest_five_band() -> None:
    out = charts.mermaid_xychart("t", ["a", "b"], [82.5, 90], y_label="kg")
    assert 'y-axis "kg" 80 --> 95' in out
    assert "bar [82.5, 90]" in out


def test_flat_series_never_collapses_the_axis() -> None:
    # All-equal non-zero-baseline values: floor((90-2.5)/5)*5=85, ceil(92.5)->95.
    out = charts.mermaid_xychart("t", ["a", "b"], [90, 90], y_label="kg")
    assert 'y-axis "kg" 85 --> 95' in out


def test_clean_strips_quotes_brackets_commas_newlines_in_all_slots() -> None:
    # Title, y-axis label AND x-axis labels must all be cleaned — a stray
    # bracket/quote/comma/newline in any of them would break the directive.
    out = charts.mermaid_xychart(
        'Squat [belt] "x"\nnext',
        ['W[1]"x"', "W2,3"],
        [1, 2],
        y_label="load, kg",
        zero_baseline=True,
    )
    assert 'title "Squat belt x next"' in out
    assert 'x-axis ["W1x", "W2 3"]' in out
    assert 'y-axis "load kg"' in out


def test_negative_zero_normalises() -> None:
    out = charts.mermaid_xychart(
        "t", ["a", "b"], [-0.0, 5], y_label="y", zero_baseline=True
    )
    assert "bar [0, 5]" in out


def test_render_is_deterministic() -> None:
    a = charts.mermaid_xychart(
        "v", ["W1", "W2", "W3"], [1000.0, 0, 2500.4], y_label="kg", zero_baseline=True
    )
    b = charts.mermaid_xychart(
        "v", ["W1", "W2", "W3"], [1000.0, 0, 2500.4], y_label="kg", zero_baseline=True
    )
    assert a == b


def test_chart_section_omits_when_no_chart() -> None:
    assert charts.chart_section("H", None) == []
    section = charts.chart_section("H", "```mermaid\nx\n```", caption="note")
    assert section[0] == "\n## H"
    assert "mermaid" in section[1]
    assert section[-1] == "\n*note*"


# --- point builders ----------------------------------------------------------


def _vol_workout(workout_id: str, start: str, weight: float) -> dict:
    return make_workout(
        workout_id,
        start=start,
        end=start.replace("17:00", "18:00"),
        exercises=[make_exercise(sets=[make_set(weight, 10)])],
    )


def test_weekly_volume_points_contiguous_iso_weeks_with_zero_gaps() -> None:
    records = build_records(
        {
            "a": _vol_workout("a", "2026-05-25T17:00:00+00:00", 100),  # vol 1000
            "b": _vol_workout("b", "2026-06-08T17:00:00+00:00", 50),  # vol 500
        }
    )
    labels, values = charts.weekly_volume_points(records, weeks=4, today=TODAY)

    assert len(labels) == len(values) == 4
    assert all(re.fullmatch(r"W\d{2}", lbl) for lbl in labels)
    # contiguous weeks, ascending, ending at the current week
    current = stats.week_start(TODAY)
    expected = [
        f"W{(current - timedelta(weeks=o)).isocalendar().week:02d}"
        for o in range(3, -1, -1)
    ]
    assert labels == expected
    assert values[-1] == 500  # this week has workout b
    assert sorted(v for v in values if v) == [500, 1000]  # gaps are zero


def test_weekly_volume_chart_disabled_when_weeks_zero() -> None:
    records = build_records({"a": _vol_workout("a", "2026-06-08T17:00:00+00:00", 50)})
    assert charts.weekly_volume_chart(records, 0, TODAY) is None


def test_e1rm_points_filters_unloaded_and_labels_mm_dd() -> None:
    records = build_records(
        {
            "a": make_workout(
                "a",
                start="2026-05-25T17:00:00+00:00",
                exercises=[make_exercise("Bench", "T-B", [make_set(60, 8)])],
            ),
            "b": make_workout(
                "b",
                start="2026-06-08T17:00:00+00:00",
                exercises=[make_exercise("Bench", "T-B", [make_set(70, 5)])],
            ),
        }
    )
    history = exercise_histories(records)["Bench"]
    labels, values = charts.e1rm_points(history, 10)

    assert labels == ["05-25", "06-08"]
    assert values == [round(epley_1rm(60, 8), 1), round(epley_1rm(70, 5), 1)]


def test_e1rm_points_widen_to_year_when_window_spans_years() -> None:
    records = build_records(
        {
            "a": make_workout(
                "a",
                start="2024-11-02T17:00:00+00:00",
                exercises=[make_exercise("Bench", "T-B", [make_set(60, 8)])],
            ),
            "b": make_workout(
                "b",
                start="2026-06-08T17:00:00+00:00",
                exercises=[make_exercise("Bench", "T-B", [make_set(70, 5)])],
            ),
        }
    )
    history = exercise_histories(records)["Bench"]
    labels, _ = charts.e1rm_points(history, 10)

    assert labels == ["24-11-02", "26-06-08"]


def test_monthly_volume_points_buckets_by_month_and_year() -> None:
    records = build_records(
        {
            "a": _vol_workout("a", "2026-03-10T17:00:00+00:00", 100),  # Mar, vol 1000
            "b": _vol_workout("b", "2026-03-20T17:00:00+00:00", 50),  # Mar, vol 500
            "c": _vol_workout("c", "2026-08-01T17:00:00+00:00", 80),  # Aug, vol 800
            "d": _vol_workout("d", "2025-03-01T17:00:00+00:00", 999),  # other year
        }
    )
    labels, values = charts.monthly_volume_points(records, 2026)

    assert labels == [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    assert len(values) == 12
    assert values[2] == 1500  # March = 1000 + 500
    assert values[7] == 800  # August
    assert sum(values) == 2300  # 2025 excluded


def test_monthly_volume_chart_renders() -> None:
    records = build_records({"a": _vol_workout("a", "2026-03-10T17:00:00+00:00", 100)})
    chart = charts.monthly_volume_chart(records, 2026)
    assert "Monthly volume 2026 (kg)" in chart
    assert 'x-axis ["Jan", "Feb"' in chart
    assert '"Dec"]' in chart


def test_e1rm_chart_none_for_bodyweight_only_exercise() -> None:
    records = build_records(
        {
            "a": make_workout(
                "a",
                start="2026-06-08T17:00:00+00:00",
                exercises=[make_exercise("Pull Up", "T-PU", [make_set(None, 12)])],
            ),
        }
    )
    history = exercise_histories(records)["Pull Up"]
    assert charts.e1rm_chart(history, 10) is None
