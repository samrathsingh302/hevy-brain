"""Dashboard, body measurement log, and weekly/monthly review notes."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..analytics import (
    comeback,
    deload,
    landmarks,
    patterns,
    session_quality,
    stats,
    strength_ratio,
)
from ..analytics.prs import recent_prs
from . import charts, heatmap
from .writer import VaultWriter, render_note

_RECENT_WORKOUTS = 10


def _link(workout_id: str, workout_paths: dict[str, str], fallback: str) -> str:
    path = workout_paths.get(workout_id, "")
    name = path.rsplit("/", 1)[-1].removesuffix(".md")
    return f"[[{name}]]" if name else fallback


def _lapse_callout(
    records: list[dict[str, Any]],
    today: date,
    nudge_days: int,
    lapse_days: int,
) -> list[str]:
    """Render a quiet-streak nudge callout for the top, or [] when none is due."""
    nudge = comeback.lapse_nudge(
        records, today, nudge_days=nudge_days, lapse_days=lapse_days
    )
    if not nudge:
        return []
    last = nudge["last_workout_date"].isoformat()
    title = nudge["last_workout_title"]
    tail = (
        "That's a lapse — run `hevy-brain guide return` for a scaled comeback plan."
        if nudge["severity"] == "lapse"
        else "Time to get back in?"
    )
    return [
        f"\n> [!warning] **{nudge['days_since']} days** since your last session "
        f"({last}, _{title}_). {tail}"
    ]


def _deload_callout(
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    today: date,
    *,
    deload_weeks: int,
    deload_rpe: float,
    plateau_weeks: int,
) -> list[str]:
    """Render the deload-readiness callout, or [] when the heuristic is silent.

    A general training-science heuristic (NOT a cited claim, NOT personalised or
    medical advice) — the label line below is mandatory whenever it fires. Fires
    only on the objective triggers in ``deload.deload_status`` and so is silent
    during a lapse.
    """
    status = deload.deload_status(
        records,
        histories,
        today,
        deload_weeks=deload_weeks,
        deload_rpe=deload_rpe,
        plateau_weeks=plateau_weeks,
    )
    if not status:
        return []
    evidence: list[str] = [f"{status['weeks']} consecutive training weeks"]
    if status["plateaus"]:
        stalled = ", ".join(status["plateaus"][:3])
        evidence.append(f"est-1RM flat on {stalled}")
    if status["mean_rpe"] is not None and status["mean_rpe"] >= status["deload_rpe"]:
        evidence.append(f"mean working-set RPE {status['mean_rpe']:.1f}")
    return [
        f"\n> [!note] Deload readiness\n"
        f"> {'; '.join(evidence)} — a lighter week may be worth considering.\n"
        "> This is a general training-science heuristic, not personalised or "
        "medical advice."
    ]


def _landmarks_lines(
    records: list[dict[str, Any]],
    today: date,
    bands: dict[str, dict[str, float]],
    *,
    landmark_weeks: int,
    templates: dict[str, dict[str, Any]] | None,
    overrides: dict[str, str] | None,
) -> list[str]:
    """Render the volume-landmark table, or [] when the check is disabled.

    A general guideline (NOT a cited claim, NOT personalised or medical advice) —
    the bands belong to the user and live in ``config.toml``; the label line below
    says so. Degrades honestly to a single "no recent training" line when the
    account is lapsed (rather than classifying stale numbers), and skips any group
    with no configured band (``other`` is always excluded).
    """
    if not bands:
        return []  # unconfigured caller -> no section at all (no orphan heading)
    status = landmarks.landmark_status(
        records,
        today,
        bands,
        landmark_weeks=landmark_weeks,
        templates=templates,
        overrides=overrides,
    )
    if status is None:
        return []
    lines = [
        "\n## Volume landmarks",
        "\n_General guideline, not personalised advice — edit the bands in "
        "`config.toml`._",
    ]
    if status["lapsed"] or not status["rows"]:
        lines.append("\nNo recent training to assess against volume landmarks.")
        return lines
    lines.append("\n| Muscle group | Sets/wk | Status |")
    lines.append("| --- | --- | --- |")
    for row in status["rows"]:
        lines.append(
            f"| {row['group']} | {row['sets_per_week']:.1f} | {row['status']} |"
        )
    return lines


def _muscle_table(volumes: dict[str, float]) -> list[str]:
    total = sum(volumes.values()) or 1.0
    lines = ["\n| Muscle group | Volume (kg) | Share |", "| --- | --- | --- |"]
    for group, volume in volumes.items():
        lines.append(f"| {group} | {volume:,.0f} | {volume / total:.0%} |")
    return lines


def _session_quality_lines(records: list[dict[str, Any]]) -> list[str]:
    """Render the Session quality block, or [] when there's nothing to show."""
    data = session_quality.session_quality(records)
    rows: list[str] = []

    time_of_day = data["time_of_day"]
    if time_of_day:
        modal = max(time_of_day, key=lambda part: time_of_day[part])
        spread = " · ".join(f"{part} {count}" for part, count in time_of_day.items())
        rows.append(f"- **When:** {spread} — most often **{modal}**")

    rpe = data["rpe"]
    if rpe["coverage"] is not None:
        rows.append(
            f"- **RPE logged:** {rpe['coverage']:.0%} of working sets "
            f"({rpe['rpe_sets']:,}/{rpe['working_sets']:,})"
        )

    duration = data["duration"]
    if duration["sessions"]:
        trend = ""
        prior_avg = duration["prior_avg_min"]
        if prior_avg is not None:
            delta = duration["recent_avg_min"] - prior_avg
            arrow = "up" if delta > 1 else "down" if delta < -1 else "flat"
            trend = f" · recent {duration['recent_avg_min']:.0f} min ({arrow})"
        rows.append(
            f"- **Duration:** avg **{duration['avg_min']:.0f} min** "
            f"(median {duration['median_min']:.0f}, range "
            f"{duration['shortest_min']:.0f}–{duration['longest_min']:.0f}){trend}"
        )

    if not rows:
        return []
    return ["\n## Session quality", *rows]


def _consistency_heatmap_lines(
    records: list[dict[str, Any]],
    today: date,
    *,
    enabled: bool,
    weeks: int,
) -> list[str]:
    """Render the consistency heatmap section, or [] when it is omitted.

    Omitted (no orphan heading) when disabled, or when ``heatmap_block`` finds
    nothing worth drawing (no working sets in the window, or <2 trained weeks).
    """
    if not enabled:
        return []
    return heatmap.heatmap_block(records, weeks, today) or []


def render_dashboard(
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    workout_paths: dict[str, str],
    store_meta: dict[str, Any],
    today: date,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
    volume_weeks: int = 0,
    lapse_nudge_days: int = 0,
    guide_lapse_days: int = 14,
    heatmap_enabled: bool = False,  # noqa: FBT001, FBT002 (append-only fence: must trail)
    heatmap_weeks: int = 26,
    deload_weeks: int = 0,
    deload_rpe: float = 8.5,
    deload_plateau_weeks: int = 4,
    landmark_weeks: int = 0,
    landmark_bands: dict[str, dict[str, float]] | None = None,
) -> str:
    """Render the main Dashboard.md (managed content)."""
    agg = stats.compute_aggregates(records, today)
    month_records = stats.records_in_range(
        records, today - timedelta(days=28), today + timedelta(days=1)
    )
    volumes_28d = patterns.volume_by_group(month_records, templates, overrides)
    ratio = patterns.push_pull_ratio(volumes_28d)
    user = store_meta.get("user") or {}

    frontmatter = {
        "updated": today.isoformat(),
        "total_workouts": agg["total_workouts"],
        "current_streak_days": agg["current_streak_days"],
        "tags": ["hevy/dashboard"],
    }

    lines = ["# Hevy Dashboard"]
    if user.get("username"):
        lines.append(f"\nAthlete: **{user['username']}**")
    lines.extend(_lapse_callout(records, today, lapse_nudge_days, guide_lapse_days))
    lines.extend(
        _deload_callout(
            records,
            histories,
            today,
            deload_weeks=deload_weeks,
            deload_rpe=deload_rpe,
            plateau_weeks=deload_plateau_weeks,
        )
    )
    lines.append(
        f"\n## Totals\n"
        f"- **{agg['total_workouts']}** workouts tracked · "
        f"**{agg['total_volume_kg']:,.0f} kg** lifetime volume\n"
        f"- Streak: **{agg['current_streak_days']}** days "
        f"(longest **{agg['longest_streak_days']}**)\n"
        f"- This week: **{agg['week_count']}** sessions, "
        f"**{agg['volume_week_kg']:,.0f} kg**, "
        f"{agg['duration_week_min']:.0f} min\n"
        f"- This month: **{agg['month_count']}** sessions, "
        f"**{agg['volume_month_kg']:,.0f} kg**\n"
        f"- This year: **{agg['year_count']}** sessions, "
        f"**{agg['volume_year_kg']:,.0f} kg**"
    )

    if volume_weeks:
        lines.extend(
            charts.chart_section(
                f"Volume trend (last {volume_weeks} weeks)",
                charts.weekly_volume_chart(records, volume_weeks, today),
            )
        )

    lines.extend(
        _consistency_heatmap_lines(
            records, today, enabled=heatmap_enabled, weeks=heatmap_weeks
        )
    )

    lines.append("\n## Muscle balance (last 28 days)")
    if volumes_28d:
        lines.extend(_muscle_table(volumes_28d))
        if ratio is not None:
            lines.append(f"\nPush/pull ratio: **{ratio:.2f}**")
    else:
        lines.append("\nNo training volume in the last 28 days.")

    lines.extend(
        _landmarks_lines(
            records,
            today,
            landmark_bands or {},
            landmark_weeks=landmark_weeks,
            templates=templates,
            overrides=overrides,
        )
    )

    lines.extend(_session_quality_lines(records))

    prs = recent_prs(histories, limit=8)
    if prs:
        lines.append("\n## Recent PRs")
        for pr in prs:
            lines.append(
                f"- {pr['date'].isoformat()} — **{pr['exercise']}** "
                f"{pr['type']} {pr['value']:.1f} kg"
            )

    lines.append("\n## Recent workouts")
    for record in list(reversed(records))[:_RECENT_WORKOUTS]:
        lines.append(
            f"- {record['start_time'].date().isoformat()} "
            f"{_link(record['id'], workout_paths, record['title'])} — "
            f"{record['volume_kg']:,.0f} kg"
        )

    lines.append(
        "\n## Browse\n- [[Body Log]]\n"
        "- `Reviews/` for weekly and monthly reviews\n"
        "- `Coach/` for AI coach recommendations"
    )
    return render_note(frontmatter, "\n".join(lines))


def _strength_to_bodyweight_lines(
    measurements: list[dict[str, Any]], histories: dict[str, dict[str, Any]]
) -> list[str]:
    """Render the strength-to-bodyweight block, or [] when it can't be computed.

    Body data is private — this lives on the Body Log only, never anything
    published.
    """
    bodyweight = strength_ratio.latest_bodyweight(measurements)
    ratios = strength_ratio.top_ratios(histories, bodyweight)
    if not ratios:
        return []
    lines = [
        "\n## Strength-to-bodyweight (latest)",
        f"\nAt **{bodyweight:g} kg** bodyweight:",
        "\n| Lift | Est. 1RM | × bodyweight |",
        "| ---- | -------- | ------------ |",
    ]
    for r in ratios:
        lines.append(f"| {r['exercise']} | {r['e1rm_kg']:.1f} kg | {r['ratio']:.2f}× |")

    top = histories.get(ratios[0]["exercise"])
    trend = strength_ratio.ratio_trend(top, measurements) if top else []
    if len(trend) >= 2:
        lines.append(f"\n## Relative strength trend — {ratios[0]['exercise']}")
        lines.append("\n| Date | Bodyweight | Est. 1RM | × bodyweight |")
        lines.append("| ---- | ---------- | -------- | ------------ |")
        for p in trend:
            lines.append(
                f"| {p['date'].isoformat()} | {p['bodyweight_kg']:g} kg "
                f"| {p['e1rm_kg']:.1f} kg | {p['ratio']:.2f}× |"
            )
    return lines


def render_body_log(
    measurements: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    today: date,
) -> str:
    """Render Measurements/Body Log.md (managed content)."""
    frontmatter = {
        "updated": today.isoformat(),
        "entries": len(measurements),
        "tags": ["hevy/measurements"],
    }
    lines = ["# Body Log"]
    if not measurements:
        lines.append("\nNo body measurements logged yet.")
    else:
        latest = measurements[-1]
        lines.append(
            f"\nLatest ({latest.get('date')}): "
            f"**{latest.get('weight_kg', '—')} kg**"
            + (
                f" · {latest['fat_percent']}% body fat"
                if latest.get("fat_percent") is not None
                else ""
            )
        )
        lines.append("\n| Date | Weight (kg) | Fat % | Lean mass (kg) |")
        lines.append("| ---- | ----------- | ----- | -------------- |")

        def cell(m: dict[str, Any], key: str) -> Any:
            value = m.get(key)
            return value if value is not None else "—"

        for m in reversed(measurements):
            lines.append(
                f"| {cell(m, 'date')} | {cell(m, 'weight_kg')} "
                f"| {cell(m, 'fat_percent')} | {cell(m, 'lean_mass_kg')} |"
            )

    lines.extend(_strength_to_bodyweight_lines(measurements, histories))
    return render_note(frontmatter, "\n".join(lines))


def _render_period_review(
    heading: str,
    frontmatter: dict[str, Any],
    period_records: list[dict[str, Any]],
    prior_records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    workout_paths: dict[str, str],
    period_start: date,
    period_end: date,
    templates: dict[str, dict[str, Any]] | None,
    overrides: dict[str, str] | None,
) -> str:
    volume = sum(r["volume_kg"] for r in period_records)
    prior_volume = sum(r["volume_kg"] for r in prior_records)
    delta = volume - prior_volume
    delta_text = f"{'+' if delta >= 0 else ''}{delta:,.0f} kg vs prior period"

    lines = [f"# {heading}"]
    lines.append(
        f"\n**{len(period_records)}** sessions · **{volume:,.0f} kg** volume "
        f"({delta_text}, prior {len(prior_records)} sessions / "
        f"{prior_volume:,.0f} kg)"
    )

    volumes = patterns.volume_by_group(period_records, templates, overrides)
    if volumes:
        lines.append("\n## Muscle balance")
        lines.extend(_muscle_table(volumes))

    period_prs = [
        {**pr, "exercise": history["title"]}
        for history in histories.values()
        for pr in history["prs"]
        if period_start <= pr["date"] < period_end
    ]
    if period_prs:
        period_prs.sort(key=lambda p: p["date"])
        lines.append("\n## PRs")
        for pr in period_prs:
            lines.append(
                f"- {pr['date'].isoformat()} — **{pr['exercise']}** "
                f"{pr['type']} {pr['value']:.1f} kg"
            )

    lines.append("\n## Sessions")
    if period_records:
        for record in period_records:
            lines.append(
                f"- {record['start_time'].date().isoformat()} "
                f"{_link(record['id'], workout_paths, record['title'])} — "
                f"{record['volume_kg']:,.0f} kg, "
                f"{record['duration_seconds'] / 60:.0f} min"
            )
    else:
        lines.append("- No sessions this period.")

    return render_note(frontmatter, "\n".join(lines))


def generate_reviews(
    writer: VaultWriter,
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    workout_paths: dict[str, str],
    today: date,
    review_weeks: int = 4,
    review_months: int = 2,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
) -> int:
    """Write weekly and monthly review notes. Returns files changed."""
    changed = 0
    current_week = stats.week_start(today)
    for offset in range(review_weeks):
        start = current_week - timedelta(weeks=offset)
        end = start + timedelta(weeks=1)
        period = stats.records_in_range(records, start, end)
        if not period and offset > 0:
            continue
        prior = stats.records_in_range(records, start - timedelta(weeks=1), start)
        iso = start.isocalendar()
        title = f"{iso.year}-W{iso.week:02d} Weekly Review"
        frontmatter = {
            "week": f"{iso.year}-W{iso.week:02d}",
            "start": start.isoformat(),
            "sessions": len(period),
            "volume_kg": round(sum(r["volume_kg"] for r in period), 1),
            "tags": ["hevy/review/weekly"],
        }
        note = _render_period_review(
            title,
            frontmatter,
            period,
            prior,
            histories,
            workout_paths,
            start,
            end,
            templates,
            overrides,
        )
        if writer.write(f"Reviews/{title}.md", note):
            changed += 1

    month_anchor = today.replace(day=1)
    for offset in range(review_months):
        year = month_anchor.year
        month = month_anchor.month - offset
        while month < 1:
            month += 12
            year -= 1
        start = date(year, month, 1)
        end = date(year + (month == 12), (month % 12) + 1, 1)
        period = stats.records_in_range(records, start, end)
        if not period and offset > 0:
            continue
        prior_start = date(year - (month == 1), month - 1 if month > 1 else 12, 1)
        prior = stats.records_in_range(records, prior_start, start)
        title = f"{start:%Y-%m} Monthly Review"
        frontmatter = {
            "month": f"{start:%Y-%m}",
            "sessions": len(period),
            "volume_kg": round(sum(r["volume_kg"] for r in period), 1),
            "tags": ["hevy/review/monthly"],
        }
        note = _render_period_review(
            title,
            frontmatter,
            period,
            prior,
            histories,
            workout_paths,
            start,
            end,
            templates,
            overrides,
        )
        if writer.write(f"Reviews/{title}.md", note):
            changed += 1
    return changed
