"""Deterministic per-lift progression targets (double progression).

Pure arithmetic on the user's *own* best recent set — "next time you do this
lift, try X kg by Y reps". This is objective progression off the logged data,
not training-science advice, so it carries no recency gate: an exercise note is
evergreen and a "next time" target is sensible even mid-lapse.

The heuristic is classic double progression: keep adding a rep until the top of
the configured range, then add a fixed load increment and reset to the bottom of
the range. A no-regression guard ensures the suggested target never estimates a
*lower* one-rep max than the basis set.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from .prs import epley_1rm


def _most_recent_session(history: dict[str, Any]) -> dict[str, Any] | None:
    """Return the chronologically latest session entry, or None if empty.

    Sessions are built in chronological order upstream, but we sort by date
    defensively rather than trust list order (spec requirement).
    """
    sessions = history.get("sessions") or []
    if not sessions:
        return None
    return max(sessions, key=lambda s: s["date"])


def next_target(history: dict[str, Any], cfg: Config) -> dict[str, Any] | None:
    """Suggest the next session's load x reps for one exercise, or None.

    Returns None (render no section) when progression is disabled, the lift has
    too little history, or the most recent top set carries no usable load
    (bodyweight-only / missing weight or reps) — there is nothing to progress.
    """
    if not cfg.progression_enabled:
        return None
    if history.get("times_performed", 0) < cfg.progression_min_sessions:
        return None

    session = _most_recent_session(history)
    if session is None:
        return None
    best_set = session.get("best_set") or {}

    weight = best_set.get("weight_kg")
    reps = best_set.get("reps")
    # No usable load (bodyweight-only / missing weight or reps) to progress.
    if weight is None or weight <= 0 or not reps:
        return None

    current_w = float(weight)
    current_r = int(reps)

    if current_r < cfg.progression_rep_high:
        target_w, target_r = current_w, current_r + 1
    else:
        target_w = round(current_w + cfg.progression_increment_kg, 1)
        target_r = cfg.progression_rep_low

    # No-regression guard: never suggest a target that estimates a lower 1RM
    # than the basis set (e.g. a low increment at the bottom of the range).
    if epley_1rm(target_w, target_r) <= epley_1rm(current_w, current_r):
        target_w, target_r = current_w, current_r + 1

    note = (
        f"Based on your best set last time ({current_w:g} kg × {current_r}), "
        f"aim for {target_w:g} kg × {target_r}."
    )
    return {
        "exercise": history["title"],
        "current_weight_kg": current_w,
        "current_reps": current_r,
        "target_weight_kg": target_w,
        "target_reps": target_r,
        "note": note,
    }
