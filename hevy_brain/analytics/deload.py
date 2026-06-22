"""Deload-readiness heuristic (S5): a deterministic "maybe deload?" signal.

This is a **general training-science heuristic**, not personalised or medical
advice and not a cited claim (the knowledge corpus carries no programming
claims — that gap is surfaced honestly elsewhere). It fires only on objective,
deterministic thresholds computed from the user's own logged training, and is
**silent during a lapse** — you cannot be "ready to deload" from training you
are not doing.

The callout fires only when ALL of these hold:
  1. a run of ``>= deload_weeks`` consecutive trained ISO-weeks ending at the
     last workout's week (an unbroken accumulation block);
  2. that run ends near now — the last workout is within ``recent_days`` of
     ``today`` (else the account is lapsed -> do not fire);
  3. a fatigue signal — at least one stalled lift (``detect_plateaus``) OR the
     mean working-set RPE over the recent window is ``>= deload_rpe``.

All arithmetic is over cached records, so a rebuild over unchanged data with the
same ``today`` is byte-identical (idempotency fence).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..models import is_warmup
from . import patterns, stats

# How close to ``today`` the run must end for the signal to be "live" rather
# than a memory of past training. ~2 weeks: one missed week is still "training".
RECENT_DAYS = 14


def _consecutive_trained_weeks(records: list[dict[str, Any]]) -> int:
    """Run length of consecutive trained ISO-weeks ending at the last workout.

    Builds the set of ISO-week Mondays that have >=1 session, then walks
    backward one week at a time from the last workout's week, counting until the
    first week with zero sessions. Returns 0 for an empty history.
    """
    if not records:
        return 0
    trained_weeks = {
        stats.week_start(r["start_time"].date()) for r in records
    }
    cursor = stats.week_start(records[-1]["start_time"].date())
    run = 0
    while cursor in trained_weeks:
        run += 1
        cursor -= timedelta(weeks=1)
    return run


def _mean_working_rpe(
    records: list[dict[str, Any]], recent_start: date
) -> float | None:
    """Mean RPE over working sets (warm-ups excluded) in the recent window.

    Only sets on or after ``recent_start`` with a non-None ``rpe`` count;
    warm-ups (``type == "warmup"``) are excluded. Returns None when no such set
    exists (so RPE simply can't be the fatigue trigger then).
    """
    rpes: list[float] = []
    for record in records:
        if record["start_time"].date() < recent_start:
            continue
        for exercise in record["exercises"]:
            for s in exercise["sets"]:
                if is_warmup(s):
                    continue
                rpe = s.get("rpe")
                if rpe is not None:
                    rpes.append(float(rpe))
    if not rpes:
        return None
    return sum(rpes) / len(rpes)


def deload_status(
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    today: date,
    *,
    deload_weeks: int,
    deload_rpe: float,
    plateau_weeks: int = 4,
) -> dict[str, Any] | None:
    """Objective deload-readiness evidence when ALL triggers hold, else None.

    Returns a dict of the evidence behind the signal::

        {"weeks": run, "plateaus": [titles], "mean_rpe": float | None,
         "deload_rpe": deload_rpe}

    Disabled (``deload_weeks <= 0``), an empty history, a run shorter than
    ``deload_weeks``, a last workout outside ``[0, RECENT_DAYS]`` days before
    ``today`` (a lapse, or a future date when ``today`` is backdated), or no
    fatigue signal each return None (no section rendered).
    """
    if deload_weeks <= 0 or not records:
        return None

    run = _consecutive_trained_weeks(records)
    if run < deload_weeks:
        return None

    last_date = records[-1]["start_time"].date()
    if not (0 <= (today - last_date).days <= RECENT_DAYS):
        return None  # lapsed, or future-dated -> not ready to deload

    plateaus = [p["exercise"] for p in patterns.detect_plateaus(
        histories, today, plateau_weeks
    )]
    recent_start = today - timedelta(weeks=plateau_weeks)
    mean_rpe = _mean_working_rpe(records, recent_start)
    high_rpe = mean_rpe is not None and mean_rpe >= deload_rpe

    if not plateaus and not high_rpe:
        return None  # consistent, but no objective fatigue signal

    return {
        "weeks": run,
        "plateaus": plateaus,
        "mean_rpe": mean_rpe,
        "deload_rpe": deload_rpe,
    }
