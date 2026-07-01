"""Tests for the F4 cache-vs-Hevy reconciliation logic (analytics.reconcile)."""

from __future__ import annotations

from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics import reconcile
from hevy_brain.analytics.prs import epley_1rm, exercise_histories
from hevy_brain.models import build_records


def _server_set(workout_id: str, weight_kg: float, reps: int) -> dict:
    """One entry of the live exercise_history list: a single logged set."""
    return {
        "workout_id": workout_id,
        "weight_kg": weight_kg,
        "reps": reps,
        "set_type": "normal",
    }


class TestResolveExercise:
    def setup_method(self) -> None:
        self.histories = {
            "Bench Press (Barbell)": {"template_id": "T-BENCH"},
            "Incline Bench Press (Dumbbell)": {"template_id": "T-INC"},
            "Bent Over Row (Barbell)": {"template_id": "T-ROW"},
        }

    def test_exact_match_case_insensitive(self) -> None:
        title, candidates = reconcile.resolve_exercise(
            self.histories, "bench press (barbell)"
        )
        assert title == "Bench Press (Barbell)"
        assert candidates == []

    def test_unique_substring_resolves(self) -> None:
        title, candidates = reconcile.resolve_exercise(self.histories, "row")
        assert title == "Bent Over Row (Barbell)"
        assert candidates == []

    def test_ambiguous_substring_returns_candidates(self) -> None:
        title, candidates = reconcile.resolve_exercise(self.histories, "bench")
        assert title is None
        assert candidates == [
            "Bench Press (Barbell)",
            "Incline Bench Press (Dumbbell)",
        ]

    def test_no_match_returns_empty(self) -> None:
        title, candidates = reconcile.resolve_exercise(self.histories, "squat")
        assert title is None
        assert candidates == []

    def test_blank_name_returns_empty(self) -> None:
        assert reconcile.resolve_exercise(self.histories, "   ") == (None, [])


class TestExtractServerSets:
    def test_live_shape_flat_set_list(self) -> None:
        """The real response: exercise_history is one entry per set."""
        payload = {
            "exercise_history": [
                _server_set("w1", 60, 8),
                _server_set("w1", 60, 8),
                _server_set("w2", 70, 5),
            ]
        }
        sets = reconcile.extract_server_sets(payload)
        assert len(sets) == 3
        assert sets[0]["weight_kg"] == 60

    def test_payload_is_a_bare_list(self) -> None:
        payload = [_server_set("w1", 60, 8), _server_set("w2", 70, 5)]
        assert len(reconcile.extract_server_sets(payload)) == 2

    def test_event_wraps_sets_shape_is_flattened(self) -> None:
        """Alternate shape: an event carrying a nested sets list — flattened,
        with the event's workout_id propagated onto each set."""
        payload = {
            "events": [{"workout_id": "w9", "sets": [make_set(80, 5), make_set(80, 4)]}]
        }
        sets = reconcile.extract_server_sets(payload)
        assert len(sets) == 2
        assert all(s["workout_id"] == "w9" for s in sets)

    def test_unrecognised_shape_returns_empty(self) -> None:
        assert reconcile.extract_server_sets({"unexpected": 42}) == []
        assert reconcile.extract_server_sets("nonsense") == []
        assert reconcile.extract_server_sets(None) == []

    def test_non_dict_rows_skipped(self) -> None:
        payload = {"exercise_history": ["junk", _server_set("w1", 60, 8), 7]}
        assert len(reconcile.extract_server_sets(payload)) == 1


class TestAggregateAndCompare:
    def test_aggregate_matches_manual(self) -> None:
        sets = [
            _server_set("w1", 60, 8),
            _server_set("w1", 60, 8),  # same workout -> still one session
            _server_set("w2", 70, 5),
        ]
        agg = reconcile.aggregate_server(sets)
        assert agg["sessions"] == 2  # distinct workout_ids, not set count
        assert agg["best_weight_kg"] == 70
        # total volume = 60*8 + 60*8 + 70*5 = 1310
        assert agg["total_volume_kg"] == 1310
        # best e1rm = max(epley(60,8), epley(70,5)) = 70*(1+5/30) = 81.66...
        assert round(agg["best_e1rm_kg"], 2) == 81.67

    def test_clean_cache_matches_server(self) -> None:
        """The key property: cache and server derive identical numbers from
        identical sets, so every row is 'ok' when nothing has drifted."""
        raw = {
            "w1": make_workout(
                "w1", exercises=[make_exercise(sets=[make_set(60, 8), make_set(60, 8)])]
            ),
            "w2": make_workout(
                "w2",
                start="2026-06-08T17:00:00+00:00",
                end="2026-06-08T18:00:00+00:00",
                exercises=[make_exercise(sets=[make_set(65, 8), make_set(70, 5)])],
            ),
        }
        histories = exercise_histories(build_records(raw))
        history = histories["Bench Press (Barbell)"]
        server_sets = [
            _server_set("w1", 60, 8),
            _server_set("w1", 60, 8),
            _server_set("w2", 65, 8),
            _server_set("w2", 70, 5),
        ]
        rows = reconcile.compare(history, reconcile.aggregate_server(server_sets))
        assert all(row["ok"] for row in rows)

    def test_extra_server_session_flags_drift(self) -> None:
        """Hevy has a workout the cache hasn't synced yet -> sessions + volume
        drift (the stale-cache signal)."""
        raw = {
            "w1": make_workout("w1", exercises=[make_exercise(sets=[make_set(60, 8)])])
        }
        history = exercise_histories(build_records(raw))["Bench Press (Barbell)"]
        server_sets = [
            _server_set("w1", 60, 8),
            _server_set("w2", 80, 5),  # a workout not in the cache
        ]
        rows = {
            r["metric"]: r
            for r in reconcile.compare(history, reconcile.aggregate_server(server_sets))
        }
        assert rows["sessions"]["ok"] is False
        assert rows["best_weight_kg"]["ok"] is False
        assert rows["total_volume_kg"]["ok"] is False

    def test_sub_kg_rounding_is_within_tolerance(self) -> None:
        history = {
            "times_performed": 1,
            "best_weight_kg": 60.0,
            "best_e1rm_kg": 76.0,
            "total_volume_kg": 480.0,
        }
        server = {
            "sessions": 1,
            "best_weight_kg": 60.3,  # < 0.5 kg
            "best_e1rm_kg": 76.0,
            "total_volume_kg": 480.2,
        }
        assert all(row["ok"] for row in reconcile.compare(history, server))

    def test_volume_tolerance_scales_with_magnitude(self) -> None:
        """A 0.6 kg gap on a large total is rounding, not drift (relative
        tolerance), but a fixed 0.5 kg floor still catches small-total gaps."""
        history = {
            "times_performed": 5,
            "best_weight_kg": 100.0,
            "best_e1rm_kg": 120.0,
            "total_volume_kg": 1_000_000.6,
        }
        server = {
            "sessions": 5,
            "best_weight_kg": 100.0,
            "best_e1rm_kg": 120.0,
            "total_volume_kg": 1_000_000.0,
        }
        rows = {r["metric"]: r for r in reconcile.compare(history, server)}
        assert rows["total_volume_kg"]["ok"] is True


def _server_warmup_set(workout_id: str, weight_kg: float, reps: int) -> dict:
    """A warm-up entry of the live exercise_history list (``set_type=warmup``)."""
    return {
        "workout_id": workout_id,
        "weight_kg": weight_kg,
        "reps": reps,
        "set_type": "warmup",
    }


class TestWarmupReconciliation:
    """Warm-ups must not inflate the server est-1RM or top weight, and a warm-up
    present in BOTH the cache and the server history must still reconcile clean
    — the load-bearing property of the prs + reconcile same-commit fix."""

    def test_aggregate_excludes_warmup_from_e1rm_and_weight(self) -> None:
        # warm-up 100x3 (Epley 110) out-Epleys AND out-weighs the working 60x8:
        # best_e1rm and best_weight both track the working set (mirroring the
        # cache's top_working_weight_kg); volume stays warm-up-inclusive.
        sets = [_server_warmup_set("w1", 100, 3), _server_set("w1", 60, 8)]
        agg = reconcile.aggregate_server(sets)
        assert agg["sessions"] == 1
        assert agg["best_weight_kg"] == 60
        assert agg["total_volume_kg"] == 100 * 3 + 60 * 8
        assert agg["best_e1rm_kg"] == epley_1rm(60, 8)

    def test_warmup_in_both_cache_and_server_reconciles_clean(self) -> None:
        raw = {
            "w1": make_workout(
                "w1",
                exercises=[
                    make_exercise(
                        sets=[make_set(100, 3, type="warmup"), make_set(60, 8)]
                    )
                ],
            )
        }
        history = exercise_histories(build_records(raw))["Bench Press (Barbell)"]
        server_sets = [_server_warmup_set("w1", 100, 3), _server_set("w1", 60, 8)]
        rows = reconcile.compare(history, reconcile.aggregate_server(server_sets))
        assert all(row["ok"] for row in rows)
