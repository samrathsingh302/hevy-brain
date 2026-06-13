"""Reconcile cache-derived exercise stats against Hevy's authoritative history.

F4 (data-integrity check). The local cache is the source of truth for the
vault, but Hevy can run *ahead* of it between syncs — a workout logged or
edited after the last sync. This module compares what we computed offline for
one exercise against the server's set-by-set history from
``GET /v1/exercise_history/{template_id}`` and reports any divergence.

It is a **staleness / integrity check, not a live read path**: the vault never
depends on it, and the network call is made only by the explicit ``verify``
command. The pure functions here take an already-fetched payload, so they stay
fully offline-testable.

The endpoint returns one entry **per logged set** under an ``exercise_history``
list (verified live 13/06/2026), each carrying ``weight_kg`` / ``reps`` and the
``workout_id`` it belongs to::

    {"exercise_history": [
        {"workout_id": "...", "weight_kg": 84, "reps": 3, "set_type": "normal", ...},
        ...
    ]}

The parser is deliberately tolerant — it searches the common keys and also
handles an event-wraps-``sets`` shape — and degrades to "no recognisable
history" rather than crashing if Hevy ever changes the shape.
"""

from __future__ import annotations

from typing import Any

from .prs import epley_1rm

# Hevy stores weights to 2dp; anything under half a kilo is rounding, not drift.
_WEIGHT_TOLERANCE_KG = 0.5
# Volume aggregates compound rounding, so the tolerance scales with magnitude.
_VOLUME_REL_TOLERANCE = 0.001


def resolve_exercise(
    histories: dict[str, dict[str, Any]], name: str
) -> tuple[str | None, list[str]]:
    """Resolve a user-typed name to a cached exercise title.

    Case-insensitive: an exact title match wins; otherwise a unique substring
    match resolves. Returns ``(title, candidates)`` — ``title`` is set only on
    a unique resolution. When it is ``None``, ``candidates`` lists the near
    misses (empty = nothing matched at all).
    """
    name_l = name.strip().lower()
    if not name_l:
        return None, []
    exact = [t for t in histories if t.lower() == name_l]
    if exact:
        return exact[0], []
    candidates = sorted(t for t in histories if name_l in t.lower())
    if len(candidates) == 1:
        return candidates[0], []
    return None, candidates


def _find_record_list(payload: Any) -> list[Any]:
    """Find the list of set records in an exercise_history payload."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("exercise_history", "events", "history", "sets", "workouts"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    nested = payload.get("exercise")
    if isinstance(nested, dict):
        for key in ("events", "history", "sets"):
            value = nested.get(key)
            if isinstance(value, list):
                return value
    # Last resort: the first list-of-dicts value we can find.
    for value in payload.values():
        if isinstance(value, list) and any(isinstance(v, dict) for v in value):
            return value
    return []


def extract_server_sets(payload: Any) -> list[dict[str, Any]]:
    """Flatten an exercise_history payload to a list of set records.

    The live shape is one entry per set (each with ``weight_kg`` / ``reps`` /
    ``workout_id``); an alternate event-wraps-``sets`` shape is also flattened,
    propagating the event's ``workout_id`` onto each set so session counting
    still works. Returns ``[]`` for an unrecognised shape (the caller reports it
    rather than treating "no data" as "matches").
    """
    sets: list[dict[str, Any]] = []
    for row in _find_record_list(payload):
        if not isinstance(row, dict):
            continue
        nested = row.get("sets")
        if isinstance(nested, list):
            workout_id = row.get("workout_id") or row.get("id")
            for s in nested:
                if isinstance(s, dict):
                    sets.append({"workout_id": workout_id, **s})
        else:
            sets.append(row)
    return sets


def aggregate_server(sets: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate the same stats the cache tracks, from flat server set records.

    ``sessions`` counts distinct ``workout_id`` values (the list itself is one
    entry per set, not per session). The rest mirror ``prs.exercise_histories``
    exactly (same Epley formula, same None→0 handling) so a clean cache produces
    identical numbers.
    """
    workout_ids: set[str] = set()
    best_weight = 0.0
    best_e1rm = 0.0
    total_volume = 0.0
    for s in sets:
        weight = float(s.get("weight_kg") or 0)
        reps = int(s.get("reps") or 0)
        best_weight = max(best_weight, weight)
        best_e1rm = max(best_e1rm, epley_1rm(weight, reps))
        total_volume += weight * reps
        workout_id = s.get("workout_id")
        if workout_id:
            workout_ids.add(workout_id)
    return {
        "sessions": len(workout_ids),
        "best_weight_kg": best_weight,
        "best_e1rm_kg": best_e1rm,
        "total_volume_kg": total_volume,
    }


def _row(
    metric: str, cache_value: float, server_value: float, tolerance: float
) -> dict[str, Any]:
    drift = abs(float(cache_value) - float(server_value))
    return {
        "metric": metric,
        "cache": cache_value,
        "server": server_value,
        "ok": drift <= tolerance,
    }


def compare(
    history: dict[str, Any], server: dict[str, Any]
) -> list[dict[str, Any]]:
    """Compare a cache history against a server aggregate; one row per metric.

    A failing row means the cache is behind Hevy for this exercise (or, rarely,
    a within-workout duplicate inflates the session count) — the signal to sync.
    """
    volume_tolerance = max(
        _WEIGHT_TOLERANCE_KG, server["total_volume_kg"] * _VOLUME_REL_TOLERANCE
    )
    return [
        _row("sessions", history["times_performed"], server["sessions"], 0),
        _row(
            "best_weight_kg",
            history["best_weight_kg"],
            server["best_weight_kg"],
            _WEIGHT_TOLERANCE_KG,
        ),
        _row(
            "best_e1rm_kg",
            history["best_e1rm_kg"],
            server["best_e1rm_kg"],
            _WEIGHT_TOLERANCE_KG,
        ),
        _row(
            "total_volume_kg",
            history["total_volume_kg"],
            server["total_volume_kg"],
            volume_tolerance,
        ),
    ]
