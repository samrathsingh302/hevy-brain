"""Per-exercise history and PR (personal record) detection."""

from __future__ import annotations

from typing import Any

from ..models import is_warmup

# Epley (like every 1RM formula) is fitted to low-rep sets and is only
# considered usable to roughly 10-12 reps; past that its linear rep term runs
# away and turns endurance work into fake strength. Unbounded, a 31.25 kg x 179
# rep cable shrug estimated a 217.7 kg "1RM" and topped the strength-to-
# bodyweight table (bug-hunt H2, 13/08/2026). Capping the rep count (rather
# than dropping the set) keeps every exercise in the table with an estimate
# that errs LOW — a set carried past the cap can only be under-credited, never
# ranked above a genuine heavy single.
EPLEY_REP_CAP = 12


def epley_1rm(weight_kg: float, reps: int) -> float:
    """Estimated one-rep max via the Epley formula, capped at 12 reps."""
    if reps <= 0 or weight_kg <= 0:
        return 0.0
    if reps == 1:
        return float(weight_kg)
    return weight_kg * (1 + min(reps, EPLEY_REP_CAP) / 30)


def _session_entry(record: dict[str, Any], exercise: dict[str, Any]) -> dict[str, Any]:
    best_e1rm = 0.0
    best_e1rm_set: dict[str, Any] | None = None
    for s in exercise["sets"]:
        if is_warmup(s):
            continue
        e1rm = epley_1rm(s.get("weight_kg") or 0, s.get("reps") or 0)
        if e1rm > best_e1rm:
            best_e1rm = e1rm
            best_e1rm_set = s
    return {
        "date": record["start_time"].date(),
        "workout_id": record["id"],
        "workout_title": record["title"],
        "top_weight_kg": exercise["top_working_weight_kg"],
        "best_e1rm_kg": best_e1rm,
        "best_set": best_e1rm_set,
        "volume_kg": exercise["volume_kg"],
        "sets": exercise["set_count"],
        "reps": exercise["total_reps"],
    }


def exercise_histories(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build per-exercise stats from chronologically sorted records.

    Returns {exercise_title: {template_id, sessions, prs, best_*, ...}}.
    PR events are recorded whenever a session beats the running best top
    weight, estimated 1RM, or session volume for that exercise.
    """
    histories: dict[str, dict[str, Any]] = {}
    for record in records:
        for exercise in record["exercises"]:
            title = exercise["title"]
            history = histories.setdefault(
                title,
                {
                    "title": title,
                    "template_id": exercise["template_id"],
                    "sessions": [],
                    "prs": [],
                    "best_weight_kg": 0.0,
                    "best_e1rm_kg": 0.0,
                    "best_session_volume_kg": 0.0,
                    "total_volume_kg": 0.0,
                },
            )
            entry = _session_entry(record, exercise)
            is_first = not history["sessions"]
            history["sessions"].append(entry)
            history["total_volume_kg"] += entry["volume_kg"]
            if exercise["template_id"]:
                history["template_id"] = exercise["template_id"]

            # First session establishes baselines without counting as a PR.
            for kind, key, best_key in (
                ("weight", "top_weight_kg", "best_weight_kg"),
                ("e1rm", "best_e1rm_kg", "best_e1rm_kg"),
                ("volume", "volume_kg", "best_session_volume_kg"),
            ):
                value = entry[key]
                if value > history[best_key]:
                    if not is_first:
                        history["prs"].append(
                            {
                                "date": entry["date"],
                                "workout_id": entry["workout_id"],
                                "type": kind,
                                "value": value,
                                "previous": history[best_key],
                            }
                        )
                    history[best_key] = value
    for history in histories.values():
        history["last_performed"] = history["sessions"][-1]["date"]
        history["times_performed"] = len(history["sessions"])
    return histories


def prs_for_workout(
    histories: dict[str, dict[str, Any]], workout_id: str
) -> list[dict[str, Any]]:
    """All PR events achieved in a given workout."""
    found: list[dict[str, Any]] = []
    for history in histories.values():
        for pr in history["prs"]:
            if pr["workout_id"] == workout_id:
                found.append({**pr, "exercise": history["title"]})
    return found


def recent_prs(
    histories: dict[str, dict[str, Any]], limit: int = 10
) -> list[dict[str, Any]]:
    """Most recent PR events across all exercises."""
    all_prs: list[dict[str, Any]] = []
    for history in histories.values():
        for pr in history["prs"]:
            all_prs.append({**pr, "exercise": history["title"]})
    all_prs.sort(key=lambda p: p["date"], reverse=True)
    return all_prs[:limit]
