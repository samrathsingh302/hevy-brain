"""Tests for A4 session-quality patterns (analytics.session_quality)."""

from __future__ import annotations

import pytest
from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics import session_quality as sq
from hevy_brain.models import build_records


def _at(workout_id: str, hour: int, *, exercises: list[dict] | None = None) -> dict:
    """A workout starting at `hour`:00 UTC, ending an hour later."""
    return make_workout(
        workout_id,
        start=f"2026-06-08T{hour:02d}:00:00+00:00",
        end=f"2026-06-08T{hour + 1:02d}:00:00+00:00",
        exercises=exercises,
    )


class TestPartOfDay:
    @pytest.mark.parametrize(
        ("hour", "expected"),
        [
            (5, "Early morning"),
            (7, "Early morning"),
            (8, "Morning"),
            (11, "Morning"),
            (12, "Afternoon"),
            (16, "Afternoon"),
            (17, "Evening"),
            (20, "Evening"),
            (21, "Night"),
            (23, "Night"),
            (0, "Night"),
            (4, "Night"),
        ],
    )
    def test_boundaries(self, hour: int, expected: str) -> None:
        assert sq.part_of_day(hour) == expected


class TestTimeOfDayCounts:
    def test_buckets_and_omits_empty(self) -> None:
        records = build_records(
            {
                "w1": _at("w1", 7),  # early morning
                "w2": _at("w2", 18),  # evening
                "w3": _at("w3", 19),  # evening
            }
        )
        counts = sq.time_of_day_counts(records)
        assert counts == {"Early morning": 1, "Evening": 2}

    def test_order_follows_time_of_day(self) -> None:
        records = build_records({"a": _at("a", 19), "b": _at("b", 9)})
        # Morning before Evening regardless of insertion order.
        assert list(sq.time_of_day_counts(records)) == ["Morning", "Evening"]


class TestRpeCoverage:
    def test_excludes_warmups(self) -> None:
        sets = [
            make_set(40, 12, type="warmup"),  # ignored
            make_set(60, 8, rpe=8),
            make_set(60, 8, rpe=9),
            make_set(60, 8),  # working, no RPE
        ]
        records = build_records(
            {"w1": _at("w1", 10, exercises=[make_exercise(sets=sets)])}
        )
        cov = sq.rpe_coverage(records)
        assert cov["working_sets"] == 3
        assert cov["rpe_sets"] == 2
        assert cov["coverage"] == pytest.approx(2 / 3)

    def test_no_working_sets_returns_none(self) -> None:
        records = build_records(
            {
                "w1": _at(
                    "w1",
                    10,
                    exercises=[make_exercise(sets=[make_set(40, 12, type="warmup")])],
                )
            }
        )
        assert sq.rpe_coverage(records)["coverage"] is None


class TestDurationSummary:
    def test_excludes_zero_duration_sessions(self) -> None:
        records = build_records(
            {
                "good": make_workout(
                    "good",
                    start="2026-06-08T10:00:00+00:00",
                    end="2026-06-08T11:00:00+00:00",
                ),
                "noend": make_workout(
                    "noend",
                    start="2026-06-09T10:00:00+00:00",
                    end=None,  # no end -> duration 0 -> excluded
                ),
            }
        )
        summary = sq.duration_summary(records)
        assert summary["sessions"] == 1
        assert summary["avg_min"] == pytest.approx(60)

    def test_recent_vs_prior_trend(self) -> None:
        # 4 sessions of 30 min then 4 of 60 min, recent_n=4.
        records = []
        for i in range(8):
            day = 8 + i
            # 30 min -> end 10:30; 60 min -> end 11:00.
            end = "10:30:00" if i < 4 else "11:00:00"
            records.append(
                make_workout(
                    f"w{i}",
                    start=f"2026-06-{day:02d}T10:00:00+00:00",
                    end=f"2026-06-{day:02d}T{end}+00:00",
                )
            )
        built = build_records({r["id"]: r for r in records})
        summary = sq.duration_summary(built, recent_n=4)
        assert summary["sessions"] == 8
        assert summary["recent_avg_min"] == pytest.approx(60)
        assert summary["prior_avg_min"] == pytest.approx(30)
        assert summary["longest_min"] == pytest.approx(60)
        assert summary["shortest_min"] == pytest.approx(30)

    def test_no_durations(self) -> None:
        records = build_records(
            {"w1": make_workout("w1", start="2026-06-08T10:00:00+00:00", end=None)}
        )
        assert sq.duration_summary(records) == {"sessions": 0}

    def test_prior_none_when_too_few_sessions(self) -> None:
        records = build_records({"w1": _at("w1", 10)})
        summary = sq.duration_summary(records, recent_n=10)
        assert summary["prior_avg_min"] is None


class TestSessionQualityRollup:
    def test_rollup_has_all_views(self) -> None:
        records = build_records({"w1": _at("w1", 18)})
        data = sq.session_quality(records)
        assert data["total_sessions"] == 1
        assert data["time_of_day"] == {"Evening": 1}
        assert "coverage" in data["rpe"]
        assert data["duration"]["sessions"] == 1
