"""One "Year in Review" note per calendar year of training.

Summarises a year from the local cache: totals, the best month, the longest
streak, most-trained lifts, that year's PRs, muscle balance, and a 12-bar
monthly-volume chart. Pure read of already-computed records/histories — no new
analytics, no network.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..analytics import patterns, stats
from . import charts
from .writer import VaultWriter, render_note

_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_PUSH_PULL_LOW = 0.85
_PUSH_PULL_HIGH = 1.15
_TOP_EXERCISES = 5
_MAX_PR_ROWS = 10


def _balance_word(ratio: float) -> str:
    if ratio > _PUSH_PULL_HIGH:
        return "push-heavy"
    if ratio < _PUSH_PULL_LOW:
        return "pull-heavy"
    return "balanced"


def _best_month(year_records: list[dict[str, Any]]) -> tuple[int, int, float] | None:
    """Return (month_number, sessions, volume_kg) for the highest-volume month."""
    by_month: dict[int, dict[str, Any]] = {}
    for record in year_records:
        month = record["start_time"].date().month
        bucket = by_month.setdefault(month, {"sessions": 0, "volume_kg": 0.0})
        bucket["sessions"] += 1
        bucket["volume_kg"] += record["volume_kg"]
    if not by_month:
        return None
    # Highest volume wins; ties broken by the earliest month (deterministic).
    month = max(by_month, key=lambda m: (by_month[m]["volume_kg"], -m))
    return month, by_month[month]["sessions"], by_month[month]["volume_kg"]


def _top_exercises(year_records: list[dict[str, Any]]) -> list[tuple[str, float, int]]:
    """Most-trained exercises in the year by total volume: (title, volume, sessions).

    Volume sums every set; ``sessions`` counts distinct workouts the lift
    appeared in (a lift logged twice in one workout is one session, not two).
    """
    volume: dict[str, float] = {}
    sessions: dict[str, int] = {}
    for record in year_records:
        for exercise in record["exercises"]:
            title = exercise["title"]
            volume[title] = volume.get(title, 0.0) + exercise["volume_kg"]
        for title in {e["title"] for e in record["exercises"]}:
            sessions[title] = sessions.get(title, 0) + 1
    ranked = sorted(volume.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(title, vol, sessions[title]) for title, vol in ranked[:_TOP_EXERCISES]]


def render_year_review(
    year: int,
    year_records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    today: date,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
) -> str:
    """Render the managed Year-in-Review note for one calendar year."""
    sessions = len(year_records)
    volume = sum(r["volume_kg"] for r in year_records)
    reps = sum(r["total_reps"] for r in year_records)
    dates = {r["start_time"].date() for r in year_records}
    # Longest run of consecutive days WITHIN this calendar year — a streak that
    # crosses 31 Dec/1 Jan is counted in each year separately. `today` is inert
    # here: only the longest value [1] is used, never the current-streak value.
    longest_streak = stats.compute_streaks(dates, today)[1]

    frontmatter = {
        "year": year,
        "sessions": sessions,
        "volume_kg": round(volume, 1),
        "active_days": len(dates),
        "tags": ["hevy/review/year"],
    }

    lines = [f"# {year} — Year in Review"]
    lines.append(
        f"\n**{sessions}** sessions across **{len(dates)}** training days · "
        f"**{volume:,.0f} kg** total volume · **{reps:,}** reps · "
        f"longest streak **{longest_streak}** days"
    )

    chart = charts.monthly_volume_chart(year_records, year)
    lines.extend(charts.chart_section("Monthly volume", chart))

    best = _best_month(year_records)
    if best:
        month, month_sessions, month_volume = best
        lines.append(
            f"\n## Best month\n**{_MONTH_NAMES[month - 1]}** — "
            f"{month_sessions} sessions, {month_volume:,.0f} kg"
        )

    volumes = patterns.volume_by_group(year_records, templates, overrides)
    if volumes:
        total = sum(volumes.values()) or 1.0
        lines.append("\n## Muscle balance")
        for group, group_volume in volumes.items():
            lines.append(
                f"- {group}: {group_volume:,.0f} kg ({group_volume / total:.0%})"
            )
        ratio = patterns.push_pull_ratio(volumes)
        if ratio is not None:
            lines.append(f"\nPush/pull ratio: **{ratio:.2f}** ({_balance_word(ratio)})")

    top = _top_exercises(year_records)
    if top:
        lines.append("\n## Most-trained exercises")
        for title, exercise_volume, exercise_sessions in top:
            lines.append(
                f"- [[{title}]] — {exercise_volume:,.0f} kg over "
                f"{exercise_sessions} sessions"
            )

    year_prs = [
        {**pr, "exercise": history["title"]}
        for history in histories.values()
        for pr in history["prs"]
        if pr["date"].year == year
    ]
    lines.append(f"\n## PRs ({len(year_prs)})")
    if year_prs:
        year_prs.sort(key=lambda p: p["date"], reverse=True)
        for pr in year_prs[:_MAX_PR_ROWS]:
            lines.append(
                f"- {pr['date'].isoformat()} — **{pr['exercise']}** "
                f"{pr['type']} {pr['value']:.1f} kg"
            )
        if len(year_prs) > _MAX_PR_ROWS:
            lines.append(f"- …and {len(year_prs) - _MAX_PR_ROWS} more")
    else:
        lines.append("- No PRs recorded this year.")

    return render_note(frontmatter, "\n".join(lines))


def generate_year_reviews(
    writer: VaultWriter,
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    today: date,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
) -> int:
    """Write one Year-in-Review note per calendar year with workouts.

    Returns the number of files changed.
    """
    years = sorted({r["start_time"].date().year for r in records})
    changed = 0
    for year in years:
        year_records = [r for r in records if r["start_time"].date().year == year]
        note = render_year_review(
            year, year_records, histories, today, templates, overrides
        )
        if writer.write(f"Reviews/{year} Year in Review.md", note):
            changed += 1
    return changed
