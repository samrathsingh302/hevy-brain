"""Objective last-vs-prior session comparison (the ``diff`` command).

Pure, offline arithmetic on the user's own logged sets: no advice, no
training-science claims, no network, no vault write. Two shapes:

* **Overall** (no exercise): the two most recent *workouts*. Reports the deltas
  of volume, duration and exercise count, and (for each exercise present in
  both sessions) how its heaviest working set moved. The session entries do not
  pre-store a (weight x reps) top set for a whole workout, so the heaviest
  non-warm-up set is found here by scanning ``record["exercises"][i]["sets"]``.
* **Per-exercise**: that exercise's two most recent *sessions* (from
  ``exercise_histories``), comparing the stored ``best_set``, estimated 1RM,
  total reps and volume.

All direction indicators are ASCII (``+`` / ``-`` / ``=``) so the report is safe
to print to a Windows cp1252 console regardless of how it is invoked.
"""

from __future__ import annotations

from typing import Any

from ..models import is_warmup
from .prs import epley_1rm

# ASCII direction indicators: never raw arrows (cp1252-safe on every path).
_UP = "+"
_DOWN = "-"
_SAME = "="


def _direction(delta: float) -> str:
    """Return an ASCII up/down/same indicator for a signed change."""
    if delta > 0:
        return _UP
    if delta < 0:
        return _DOWN
    return _SAME


def _fmt_delta(delta: float, unit: str = "") -> str:
    """Format a signed, British-style delta, e.g. ``+1,250 kg`` or ``-3``.

    Whole-number magnitudes drop the decimals; the sign is always explicit so a
    no-change reads as ``+0``.
    """
    suffix = f" {unit}" if unit else ""
    if float(delta).is_integer():
        return f"{delta:+,.0f}{suffix}"
    return f"{delta:+,.1f}{suffix}"


def _heaviest_working_set(exercise: dict[str, Any]) -> dict[str, Any] | None:
    """Return the heaviest non-warm-up set of an exercise (None if none).

    Warm-ups (``type == "warmup"``) are excluded. Bodyweight sets carry
    ``weight_kg=None``; they count as 0 kg for the comparison but are still
    eligible when an exercise has only bodyweight sets.
    """
    best: dict[str, Any] | None = None
    best_weight = -1.0
    for s in exercise.get("sets", []):
        if is_warmup(s):
            continue
        weight = float(s.get("weight_kg") or 0)
        if weight > best_weight:
            best_weight = weight
            best = s
    return best


def _set_label(workout_set: dict[str, Any] | None) -> str:
    """Render a set as ``W kg x R`` (ASCII), or ``(none)`` when absent."""
    if not workout_set:
        return "(none)"
    weight = workout_set.get("weight_kg")
    reps = workout_set.get("reps") or 0
    if not weight:
        return f"bodyweight x {reps}"
    return f"{float(weight):g} kg x {reps}"


def _top_set_weight(workout_set: dict[str, Any] | None) -> float:
    if not workout_set:
        return 0.0
    return float(workout_set.get("weight_kg") or 0)


def overall_diff(
    prior: dict[str, Any], latest: dict[str, Any]
) -> dict[str, Any]:
    """Compare two whole workouts (``prior`` then ``latest``, chronological).

    Returns the headline deltas plus, for every exercise trained in both, the
    heaviest-working-set change, and the titles added/dropped between them.
    """
    prior_min = round(prior["duration_seconds"] / 60)
    latest_min = round(latest["duration_seconds"] / 60)

    prior_by_title = {e["title"]: e for e in prior["exercises"]}
    latest_by_title = {e["title"]: e for e in latest["exercises"]}
    shared = [t for t in latest_by_title if t in prior_by_title]

    exercises: list[dict[str, Any]] = []
    for title in shared:
        prior_set = _heaviest_working_set(prior_by_title[title])
        latest_set = _heaviest_working_set(latest_by_title[title])
        weight_delta = _top_set_weight(latest_set) - _top_set_weight(prior_set)
        exercises.append(
            {
                "exercise": title,
                "prior_set": prior_set,
                "latest_set": latest_set,
                "weight_delta_kg": weight_delta,
            }
        )

    added = sorted(t for t in latest_by_title if t not in prior_by_title)
    dropped = sorted(t for t in prior_by_title if t not in latest_by_title)

    return {
        "prior_date": prior["start_time"].date(),
        "latest_date": latest["start_time"].date(),
        "volume_delta_kg": latest["volume_kg"] - prior["volume_kg"],
        "prior_volume_kg": prior["volume_kg"],
        "latest_volume_kg": latest["volume_kg"],
        "duration_delta_min": latest_min - prior_min,
        "prior_duration_min": prior_min,
        "latest_duration_min": latest_min,
        "exercise_count_delta": latest["exercise_count"] - prior["exercise_count"],
        "prior_exercise_count": prior["exercise_count"],
        "latest_exercise_count": latest["exercise_count"],
        "exercises": exercises,
        "added": added,
        "dropped": dropped,
    }


def _session_e1rm(session: dict[str, Any]) -> float:
    """Return a session's best est-1RM (stored value, or Epley from best_set)."""
    stored = session.get("best_e1rm_kg") or 0.0
    if stored:
        return float(stored)
    best = session.get("best_set")
    if best:
        return epley_1rm(best.get("weight_kg") or 0, best.get("reps") or 0)
    return 0.0


def exercise_diff(history: dict[str, Any]) -> dict[str, Any]:
    """Compare an exercise's two most recent sessions (chronological).

    ``history`` is one entry from ``exercise_histories``; its ``sessions`` are
    sorted by date here (never assume order) and the last two are compared on
    top set, estimated 1RM, total reps and volume.
    """
    sessions = sorted(history["sessions"], key=lambda s: s["date"])
    prior, latest = sessions[-2], sessions[-1]

    prior_e1rm = _session_e1rm(prior)
    latest_e1rm = _session_e1rm(latest)
    prior_top = _top_set_weight(prior.get("best_set"))
    latest_top = _top_set_weight(latest.get("best_set"))

    return {
        "exercise": history["title"],
        "prior_date": prior["date"],
        "latest_date": latest["date"],
        "prior_set": prior.get("best_set"),
        "latest_set": latest.get("best_set"),
        "top_weight_delta_kg": latest_top - prior_top,
        "prior_e1rm_kg": prior_e1rm,
        "latest_e1rm_kg": latest_e1rm,
        "e1rm_delta_kg": latest_e1rm - prior_e1rm,
        "prior_reps": prior.get("reps") or 0,
        "latest_reps": latest.get("reps") or 0,
        "reps_delta": (latest.get("reps") or 0) - (prior.get("reps") or 0),
        "prior_volume_kg": prior.get("volume_kg") or 0.0,
        "latest_volume_kg": latest.get("volume_kg") or 0.0,
        "volume_delta_kg": (latest.get("volume_kg") or 0.0)
        - (prior.get("volume_kg") or 0.0),
    }


def render_overall(diff: dict[str, Any]) -> list[str]:
    """Render the overall (whole-workout) diff as ASCII stdout lines."""
    lines = [
        f"Last two sessions: {diff['prior_date'].isoformat()} "
        f"-> {diff['latest_date'].isoformat()}",
        f"  {_direction(diff['volume_delta_kg'])} volume    "
        f"{diff['prior_volume_kg']:,.0f} -> {diff['latest_volume_kg']:,.0f} kg "
        f"({_fmt_delta(diff['volume_delta_kg'], 'kg')})",
        f"  {_direction(diff['duration_delta_min'])} duration  "
        f"{diff['prior_duration_min']} -> {diff['latest_duration_min']} min "
        f"({_fmt_delta(diff['duration_delta_min'], 'min')})",
        f"  {_direction(diff['exercise_count_delta'])} exercises "
        f"{diff['prior_exercise_count']} -> {diff['latest_exercise_count']} "
        f"({_fmt_delta(diff['exercise_count_delta'])})",
    ]
    if diff["exercises"]:
        lines.append("\nTop working set, exercises trained in both:")
        for item in diff["exercises"]:
            lines.append(
                f"  {_direction(item['weight_delta_kg'])} {item['exercise']}: "
                f"{_set_label(item['prior_set'])} -> "
                f"{_set_label(item['latest_set'])} "
                f"({_fmt_delta(item['weight_delta_kg'], 'kg')} top set)"
            )
    if diff["added"]:
        lines.append("\nAdded this session: " + ", ".join(diff["added"]))
    if diff["dropped"]:
        lines.append("Dropped since last: " + ", ".join(diff["dropped"]))
    return lines


def render_exercise(diff: dict[str, Any]) -> list[str]:
    """Render the per-exercise diff as ASCII stdout lines."""
    return [
        f"{diff['exercise']}: {diff['prior_date'].isoformat()} "
        f"-> {diff['latest_date'].isoformat()}",
        f"  {_direction(diff['top_weight_delta_kg'])} top set   "
        f"{_set_label(diff['prior_set'])} -> {_set_label(diff['latest_set'])} "
        f"({_fmt_delta(diff['top_weight_delta_kg'], 'kg')})",
        f"  {_direction(diff['e1rm_delta_kg'])} est 1RM   "
        f"{diff['prior_e1rm_kg']:.1f} -> {diff['latest_e1rm_kg']:.1f} kg "
        f"({_fmt_delta(diff['e1rm_delta_kg'], 'kg')})",
        f"  {_direction(diff['reps_delta'])} reps      "
        f"{diff['prior_reps']} -> {diff['latest_reps']} "
        f"({_fmt_delta(diff['reps_delta'])})",
        f"  {_direction(diff['volume_delta_kg'])} volume    "
        f"{diff['prior_volume_kg']:,.0f} -> {diff['latest_volume_kg']:,.0f} kg "
        f"({_fmt_delta(diff['volume_delta_kg'], 'kg')})",
    ]
