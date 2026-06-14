"""Tests for guide-draft adherence (coach.adherence) — the C1 extension."""

from __future__ import annotations

from datetime import date

from conftest import make_exercise, make_set, make_workout

from hevy_brain.coach import adherence
from hevy_brain.models import build_records

PUSHED = date(2026, 6, 13)


def _body(title: str, exercises: list[dict]) -> dict:
    return {"routine": {"title": title, "exercises": exercises}}


def _ex(template_id: str, *weights: float) -> dict:
    return {
        "exercise_template_id": template_id,
        "sets": [{"weight_kg": w, "reps": 8} for w in weights],
    }


def _trained(template_id: str, title: str, weight: float, *, day: int) -> dict:
    """A post-push workout training `template_id` at `weight`."""
    return make_workout(
        f"w-{template_id}-{day}",
        start=f"2026-06-{day:02d}T17:00:00+00:00",
        end=f"2026-06-{day:02d}T18:00:00+00:00",
        exercises=[make_exercise(title, template_id, [make_set(weight, 8)])],
    )


class TestDraftKind:
    def test_return(self) -> None:
        assert adherence.draft_kind("Return Week 1 — upper") == "return"

    def test_redesign(self) -> None:
        assert adherence.draft_kind("Redesign — push 1") == "redesign"

    def test_not_a_draft(self) -> None:
        assert adherence.draft_kind("upper") is None


class TestBuildTarget:
    def test_return_draft_records_top_weights(self) -> None:
        body = _body(
            "Return Week 1 — upper",
            [_ex("T-BENCH", 45, 47.5, 47.5), _ex("T-ROW", 40)],
        )
        target = adherence.build_target(body, PUSHED)
        assert target is not None
        assert target["pushed_on"] == "2026-06-13"
        assert target["kind"] == "return"
        assert target["prescribed"] == [
            {"template_id": "T-BENCH", "top_weight_kg": 47.5, "sets": 3},
            {"template_id": "T-ROW", "top_weight_kg": 40, "sets": 1},
        ]

    def test_non_draft_returns_none(self) -> None:
        assert (
            adherence.build_target(_body("upper", [_ex("T-BENCH", 60)]), PUSHED) is None
        )

    def test_bodyweight_exercise_has_no_target_weight(self) -> None:
        body = _body(
            "Redesign — pull",
            [
                {
                    "exercise_template_id": "T-PULLUP",
                    "sets": [{"weight_kg": None, "reps": 10}],
                }
            ],
        )
        target = adherence.build_target(body, PUSHED)
        assert target["prescribed"][0]["top_weight_kg"] is None

    def test_no_usable_exercises_returns_none(self) -> None:
        assert adherence.build_target(_body("Return Week 1 — x", []), PUSHED) is None


class TestRecordAndLatest:
    def test_append_and_latest(self) -> None:
        meta: dict = {}
        adherence.record_target(meta, {"pushed_on": "2026-06-01", "routine_title": "a"})
        adherence.record_target(meta, {"pushed_on": "2026-06-13", "routine_title": "b"})
        assert adherence.latest_target(meta)["routine_title"] == "b"

    def test_bounded_history(self) -> None:
        meta: dict = {}
        for i in range(10):
            adherence.record_target(meta, {"pushed_on": f"2026-06-{i + 1:02d}"})
        assert len(meta[adherence.META_KEY]) == 6

    def test_latest_tolerates_garbage(self) -> None:
        assert adherence.latest_target({}) is None
        assert adherence.latest_target({adherence.META_KEY: "nonsense"}) is None
        assert adherence.latest_target({adherence.META_KEY: [42]}) is None


class TestGradeTarget:
    def _target(self) -> dict:
        return {
            "pushed_on": "2026-06-13",
            "routine_title": "Return Week 1 — upper",
            "kind": "return",
            "prescribed": [
                {"template_id": "T-BENCH", "top_weight_kg": 47.5, "sets": 3},
                {"template_id": "T-ROW", "top_weight_kg": 40, "sets": 3},
            ],
        }

    def test_none_target(self) -> None:
        assert adherence.grade_target(None, []) is None

    def test_no_workouts_since_push(self) -> None:
        out = adherence.grade_target(self._target(), [])
        assert "hasn't been trained yet" in out

    def test_on_target_and_not_trained(self) -> None:
        records = build_records(
            {"w1": _trained("T-BENCH", "Bench", 47.5, day=14)}  # row not trained
        )
        out = adherence.grade_target(
            self._target(),
            records,
            templates={"T-BENCH": {"title": "Bench Press"}},
        )
        assert "on target (100%)" in out
        assert "Bench Press" in out  # label resolved from templates
        assert "not trained yet" in out  # T-ROW
        assert "Trained **1/2**" in out

    def test_under_and_above_target(self) -> None:
        records = build_records(
            {
                "w1": _trained("T-BENCH", "Bench", 40, day=14),  # 40/47.5 = 84%
                "w2": _trained("T-ROW", "Row", 44, day=15),  # 44/40 = 110%
            }
        )
        out = adherence.grade_target(self._target(), records)
        assert "under target (84%)" in out
        assert "above target (110%)" in out
        assert "Trained **2/2**" in out

    def test_only_workouts_after_push_count(self) -> None:
        records = build_records(
            {
                "before": _trained("T-BENCH", "Bench", 47.5, day=10),  # before push
                "after": _trained("T-ROW", "Row", 40, day=14),
            }
        )
        out = adherence.grade_target(self._target(), records)
        # Bench was only trained before the push -> still not trained "since".
        assert "not trained yet" in out

    def test_bodyweight_not_load_graded(self) -> None:
        target = {
            "pushed_on": "2026-06-13",
            "routine_title": "Redesign — pull",
            "prescribed": [
                {"template_id": "T-PULLUP", "top_weight_kg": None, "sets": 3}
            ],
        }
        records = build_records({"w1": _trained("T-PULLUP", "Pull Up", 0, day=14)})
        out = adherence.grade_target(target, records)
        assert "load not graded" in out

    def test_malformed_items_skipped(self) -> None:
        target = {
            "pushed_on": "2026-06-13",
            "routine_title": "Return Week 1 — x",
            "prescribed": [
                "junk",
                {"top_weight_kg": 50},
                {"template_id": "T-BENCH", "top_weight_kg": 47.5},
            ],
        }
        records = build_records({"w1": _trained("T-BENCH", "Bench", 47.5, day=14)})
        out = adherence.grade_target(target, records)
        assert "Trained **1/1**" in out  # only the one valid item counts
