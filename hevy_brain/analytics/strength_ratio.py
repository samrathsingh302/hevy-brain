"""Strength-to-bodyweight ratios (A5) — vault-local relative-strength insight.

Pairs bodyweight (from body measurements) with estimated 1RMs (from exercise
histories) to show how strong you are *for your size*, and how that ratio has
trended. Bodyweight is private body data, so this surfaces only on the Body Log
note — never on anything published (the locked CV-readiness decision).
"""

from __future__ import annotations

from datetime import date
from typing import Any


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def bodyweight_points(measurements: list[dict[str, Any]]) -> list[tuple[date, float]]:
    """Sorted ``(date, weight_kg)`` for measurements with a usable bodyweight."""
    points: list[tuple[date, float]] = []
    for m in measurements:
        day = _parse_date(m.get("date"))
        weight = m.get("weight_kg")
        if day is not None and weight:
            points.append((day, float(weight)))
    points.sort()
    return points


def latest_bodyweight(measurements: list[dict[str, Any]]) -> float | None:
    """Most recently measured bodyweight, or None if none is recorded."""
    points = bodyweight_points(measurements)
    return points[-1][1] if points else None


def top_ratios(
    histories: dict[str, dict[str, Any]],
    bodyweight: float | None,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Top weighted lifts by est-1RM with their strength-to-bodyweight ratio.

    Weighted lifts only (``best_e1rm_kg > 0``) — a bodyweight exercise has no
    meaningful external-load ratio. Ranked by est-1RM, title breaking ties so
    the order is deterministic.
    """
    if not bodyweight or bodyweight <= 0:
        return []
    weighted = [h for h in histories.values() if h.get("best_e1rm_kg", 0) > 0]
    weighted.sort(key=lambda h: (-h["best_e1rm_kg"], h["title"]))
    return [
        {
            "exercise": h["title"],
            "e1rm_kg": h["best_e1rm_kg"],
            "ratio": h["best_e1rm_kg"] / bodyweight,
        }
        for h in weighted[:limit]
    ]


def best_e1rm_as_of(history: dict[str, Any], cutoff: date) -> float:
    """Best est-1RM from this lift's sessions on or before ``cutoff`` (0 if none)."""
    return max(
        (s["best_e1rm_kg"] for s in history["sessions"] if s["date"] <= cutoff),
        default=0.0,
    )


def ratio_trend(
    history: dict[str, Any],
    measurements: list[dict[str, Any]],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Relative-strength trend for one lift across recent measurement dates.

    For each bodyweight point, pair the bodyweight with the best est-1RM
    achieved up to that date. Dates before the lift's first session (no est-1RM
    yet) are skipped. Returns the most recent ``limit`` points.
    """
    points: list[dict[str, Any]] = []
    for day, weight in bodyweight_points(measurements):
        e1rm = best_e1rm_as_of(history, day)
        if e1rm > 0:
            points.append(
                {
                    "date": day,
                    "bodyweight_kg": weight,
                    "e1rm_kg": e1rm,
                    "ratio": e1rm / weight,
                }
            )
    return points[-limit:]
