"""Coach memory: an objective focus snapshot + an honest "since last time" recap.

Each coach run persists a small, fully machine-derived snapshot (consistency,
push/pull ratio, the plateaus it flagged with their estimated 1RM) into
``store.meta``. The next run re-derives those metrics from *newer* logged
workouts and grades each one — improved / held / regressed / can't-grade —
purely by comparing old numbers to new numbers.

It NEVER reads or judges the recommendations Claude writes below the
``%% hevy-brain:end %%`` marker (those are free text, opaque to hevy-brain). It
grades the objective *situation* the advice addressed, against later real Hevy
data, and says so. This keeps the feature inside the repo's honesty/provenance
discipline: data is data, judgement stays with the reader.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..analytics import patterns, stats
from ..analytics.prs import recent_prs

META_KEY = "coach_focus"
_KEEP = 12
# A lift's est. 1RM must move more than this (kg) to count as a real change —
# below it is float/rounding noise and grades as "held".
_E1RM_TOLERANCE_KG = 0.5
# Push/pull ratios inside this band are treated as balanced.
_BALANCE_LOW = 0.85
_BALANCE_HIGH = 1.15


def _signals(
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    today: date,
    *,
    plateau_weeks: int,
    templates: dict[str, dict[str, Any]] | None,
    overrides: dict[str, str] | None,
) -> tuple[dict[str, Any], float | None, list[dict[str, Any]]]:
    """Recompute the objective signals a snapshot/recap is built from."""
    agg = stats.compute_aggregates(records, today)
    recent = stats.records_in_range(
        records, today - timedelta(days=28), today + timedelta(days=1)
    )
    ratio = patterns.push_pull_ratio(
        patterns.volume_by_group(recent, templates, overrides)
    )
    plateaus = patterns.detect_plateaus(histories, today, plateau_weeks)
    return agg, ratio, plateaus


def build_focus_snapshot(
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    today: date,
    *,
    path: str,
    plateau_weeks: int,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Capture the objective focus of this coach run, for the next run to grade."""
    agg, ratio, plateaus = _signals(
        records,
        histories,
        today,
        plateau_weeks=plateau_weeks,
        templates=templates,
        overrides=overrides,
    )
    return {
        "taken_on": today.isoformat(),
        "path": path,
        "sessions_last_7d": agg["week_count"],
        "current_streak_days": agg["current_streak_days"],
        "push_pull_ratio": ratio,
        "plateau_weeks": plateau_weeks,
        "plateaus": [
            {"exercise": p["exercise"], "e1rm_kg": round(p["best_recent_e1rm_kg"], 1)}
            for p in plateaus
        ],
    }


def latest_focus(meta: dict[str, Any]) -> dict[str, Any] | None:
    """Return the most recent prior focus snapshot, or None if there isn't one."""
    snapshots = meta.get(META_KEY)
    if isinstance(snapshots, list) and snapshots:
        last = snapshots[-1]
        return last if isinstance(last, dict) else None
    return None


def record_focus(meta: dict[str, Any], snapshot: dict[str, Any]) -> None:
    """Append a snapshot to the bounded history in meta (keeps the last _KEEP)."""
    snapshots = meta.setdefault(META_KEY, [])
    snapshots.append(snapshot)
    meta[META_KEY] = snapshots[-_KEEP:]


def _balance_word(ratio: float) -> str:
    if ratio > _BALANCE_HIGH:
        return "push-heavy"
    if ratio < _BALANCE_LOW:
        return "pull-heavy"
    return "balanced"


def _grade_plateau(
    item: Any, histories: dict[str, dict[str, Any]], prev_date: date
) -> str | None:
    """Grade whether the flagged lift's est. 1RM moved since prev_date.

    Returns None for a malformed plateau item (e.g. a hand-edited meta.json):
    a corrupt snapshot must never crash the coach run.
    """
    if not isinstance(item, dict) or not item.get("exercise"):
        return None
    exercise = item["exercise"]
    try:
        old = float(item.get("e1rm_kg") or 0.0)
    except (TypeError, ValueError):
        old = 0.0
    history = histories.get(exercise)
    sessions = (
        [s for s in history["sessions"] if s["date"] > prev_date] if history else []
    )
    if not sessions:
        return (
            f"- **{exercise}** plateau (e1RM {old:g} kg): not trained since "
            f"— **can't grade**"
        )
    new_best = round(max(s["best_e1rm_kg"] for s in sessions), 1)
    n = len(sessions)
    sess = "session" if n == 1 else "sessions"
    if new_best > old + _E1RM_TOLERANCE_KG:
        verdict = "improved"
    elif new_best < old - _E1RM_TOLERANCE_KG:
        verdict = "regressed"
    else:
        verdict = "held"
    return (
        f"- **{exercise}** plateau: e1RM {old:g} kg → {new_best:g} kg over "
        f"{n} {sess} — **{verdict}**"
    )


def grade_focus(
    prev: dict[str, Any] | None,
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    today: date,
    *,
    plateau_weeks: int,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
) -> str | None:
    """Render a "Since your last briefing" recap, or None if there's no prior run.

    Grades only objective, hevy-brain-computed metrics against workouts logged
    after the prior snapshot — never the written advice.
    """
    if not prev or not prev.get("taken_on"):
        return None
    try:
        prev_date = date.fromisoformat(prev["taken_on"])
    except (ValueError, TypeError):
        return None

    new_records = [r for r in records if r["start_time"].date() > prev_date]
    header = [
        "## Since your last briefing",
        (
            f"_Graded from workouts logged since {prev_date.isoformat()} — "
            "objective data only, not a judgement of the written advice._"
        ),
    ]
    callout = (
        "\n> [!note] This grades the situation your last briefing addressed, "
        "not the recommendations themselves — those are written below the "
        "marker, where hevy-brain can't read them."
    )

    if not new_records:
        body = [
            f"\n_No workouts logged since {prev_date.isoformat()} — "
            "nothing to grade yet._"
        ]
        return "\n".join(header + body) + callout

    lines: list[str] = [f"\n- Sessions logged since: **{len(new_records)}**"]

    new_prs = [pr for pr in recent_prs(histories, limit=100) if pr["date"] > prev_date]
    if new_prs:
        shown = ", ".join(
            f"{pr['exercise']} {pr['type']} {pr['value']:.1f} kg" for pr in new_prs[:4]
        )
        more = f" (+{len(new_prs) - 4} more)" if len(new_prs) > 4 else ""
        lines.append(f"- New PRs since: **{len(new_prs)}** — {shown}{more}")

    plateaus = prev.get("plateaus")
    for item in plateaus if isinstance(plateaus, list) else []:
        line = _grade_plateau(item, histories, prev_date)
        if line:
            lines.append(line)

    agg, ratio, _ = _signals(
        records,
        histories,
        today,
        plateau_weeks=plateau_weeks,
        templates=templates,
        overrides=overrides,
    )
    prev_week = prev.get("sessions_last_7d")
    if isinstance(prev_week, int) and not isinstance(prev_week, bool):
        now_week = agg["week_count"]
        if now_week > prev_week:
            trend = "up"
        elif now_week < prev_week:
            trend = "down"
        else:
            trend = "flat"
        lines.append(
            f"- Consistency: {prev_week} → {now_week} sessions in the last "
            f"7 days — **{trend}**"
        )

    prev_ratio = prev.get("push_pull_ratio")
    if (
        isinstance(prev_ratio, (int, float))
        and not isinstance(prev_ratio, bool)
        and ratio is not None
    ):
        moved = abs(ratio - 1.0) < abs(prev_ratio - 1.0) - 0.05
        drifted = abs(ratio - 1.0) > abs(prev_ratio - 1.0) + 0.05
        note = (
            "rebalancing toward 1.0"
            if moved
            else "drifting from balance"
            if drifted
            else f"steady ({_balance_word(ratio)})"
        )
        lines.append(
            f"- Push/pull balance: {prev_ratio:.2f} → {ratio:.2f} — **{note}**"
        )

    return "\n".join(header + lines) + callout
