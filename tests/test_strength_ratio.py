"""Tests for A5 strength-to-bodyweight ratios (analytics.strength_ratio)."""

from __future__ import annotations

from datetime import date

import pytest

from hevy_brain.analytics import strength_ratio as sr


def _measure(day: str, weight: float | None) -> dict:
    return {"date": day, "weight_kg": weight}


def _history(title: str, e1rm: float, sessions: list[dict] | None = None) -> dict:
    return {"title": title, "best_e1rm_kg": e1rm, "sessions": sessions or []}


def _session(day: date, e1rm: float) -> dict:
    return {"date": day, "best_e1rm_kg": e1rm}


class TestBodyweightPoints:
    def test_sorts_and_drops_unusable(self) -> None:
        measurements = [
            _measure("2026-03-01", 80),
            _measure("2026-01-01", 82),
            _measure("2026-02-01", None),  # no weight -> dropped
            {"date": "not-a-date", "weight_kg": 99},  # bad date -> dropped
        ]
        points = sr.bodyweight_points(measurements)
        assert points == [(date(2026, 1, 1), 82.0), (date(2026, 3, 1), 80.0)]

    def test_latest_bodyweight(self) -> None:
        assert sr.latest_bodyweight([_measure("2026-01-01", 82), _measure("2026-03-01", 80)]) == 80
        assert sr.latest_bodyweight([]) is None
        assert sr.latest_bodyweight([_measure("2026-01-01", None)]) is None


class TestTopRatios:
    def _histories(self) -> dict:
        return {
            "Bench": _history("Bench", 100.0),
            "Squat": _history("Squat", 140.0),
            "Pull Up": _history("Pull Up", 0.0),  # bodyweight -> excluded
        }

    def test_ratio_and_ordering(self) -> None:
        ratios = sr.top_ratios(self._histories(), 80.0)
        assert [r["exercise"] for r in ratios] == ["Squat", "Bench"]
        assert ratios[0]["ratio"] == pytest.approx(1.75)
        assert ratios[1]["ratio"] == pytest.approx(1.25)

    def test_excludes_bodyweight_lifts(self) -> None:
        assert all(r["exercise"] != "Pull Up" for r in sr.top_ratios(self._histories(), 80))

    def test_limit(self) -> None:
        assert len(sr.top_ratios(self._histories(), 80, limit=1)) == 1

    def test_no_bodyweight_returns_empty(self) -> None:
        assert sr.top_ratios(self._histories(), None) == []
        assert sr.top_ratios(self._histories(), 0) == []

    def test_tie_breaks_on_title(self) -> None:
        histories = {"B lift": _history("B lift", 100.0), "A lift": _history("A lift", 100.0)}
        assert [r["exercise"] for r in sr.top_ratios(histories, 80)] == ["A lift", "B lift"]


class TestBestE1rmAsOf:
    def test_max_up_to_cutoff(self) -> None:
        history = _history("Bench", 100, [_session(date(2026, 1, 1), 80), _session(date(2026, 3, 1), 100)])
        assert sr.best_e1rm_as_of(history, date(2026, 2, 15)) == 80
        assert sr.best_e1rm_as_of(history, date(2026, 3, 1)) == 100

    def test_zero_before_first_session(self) -> None:
        history = _history("Bench", 100, [_session(date(2026, 1, 1), 80)])
        assert sr.best_e1rm_as_of(history, date(2025, 12, 1)) == 0.0


class TestRatioTrend:
    def test_pairs_and_skips_pre_session_dates(self) -> None:
        history = _history(
            "Bench", 100, [_session(date(2026, 1, 1), 80), _session(date(2026, 3, 1), 100)]
        )
        measurements = [
            _measure("2025-12-01", 82),  # before first session -> skipped
            _measure("2026-02-01", 80),  # e1rm 80 -> ratio 1.0
            _measure("2026-04-01", 78),  # e1rm 100 -> ratio ~1.28
        ]
        trend = sr.ratio_trend(history, measurements)
        assert len(trend) == 2
        assert trend[0]["ratio"] == pytest.approx(1.0)
        assert trend[1]["ratio"] == pytest.approx(100 / 78)
        # Relative strength rose even as bodyweight fell.
        assert trend[1]["ratio"] > trend[0]["ratio"]

    def test_limit_keeps_most_recent(self) -> None:
        sessions = [_session(date(2026, 1, 1), 50)]
        history = _history("Bench", 50, sessions)
        measurements = [_measure(f"2026-0{i}-01", 80) for i in range(2, 8)]  # 6 points
        trend = sr.ratio_trend(history, measurements, limit=3)
        assert len(trend) == 3
        assert trend[-1]["date"] == date(2026, 7, 1)
