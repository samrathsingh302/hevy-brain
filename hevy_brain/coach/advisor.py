"""AI coach: turns analytics into grounded, structured recommendations.

Uses the Anthropic API with structured outputs so every recommendation is
machine-readable. Coach failures must never break a sync — callers should
catch CoachError and continue.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..analytics import patterns, stats
from ..analytics.prs import recent_prs
from ..clock import now_london
from ..knowledge import Claim
from ..vault.writer import render_note

DEFAULT_MODEL = "claude-opus-4-8"

# Provenance labels for every guidance claim in coach output (E5).
PROVENANCE_VALUES = ("cited", "general-knowledge")
Provenance = Literal["cited", "general-knowledge"]

PROVENANCE_RULES = """\
Provenance (mandatory honesty rule):
- For every training-science assertion (not data observations), set
  `provenance`: use `cited` ONLY when the claim is supported by one of the
  supplied Knowledge-base claims, and put that claim's exact `[[id#^claim-xx]]`
  link in `claim_link`. Otherwise set `provenance` to `general-knowledge` and
  leave `claim_link` empty.
- NEVER present general knowledge as cited, and never invent a citation link.
  If the Knowledge base is silent on a point you need (e.g. hypertrophy
  programming or nutrition targets), say so as a corpus/ingestion gap rather
  than fabricating support.
"""

SYSTEM_PROMPT = f"""\
You are a strength-training coach analyzing one athlete's real Hevy workout
data. You receive computed statistics (volume, PRs, plateaus, muscle balance,
week-over-week changes), the athlete's recent training history, and — when
available — a "Knowledge base" of cited claims distilled from sports-science
podcasts (each with an evidence tag and an `[[id#^claim-xx]]` link).

Rules:
- Ground EVERY data claim in the supplied data: cite the exact numbers and
  dates you are reasoning from in the `evidence` field.
- Never invent workouts, weights, or dates that are not in the data.
- Recommendations must be specific and actionable (sets, reps, loads,
  frequency), not generic advice.
- When you recommend swapping an exercise, choose the replacement ONLY from
  the "available exercises" list supplied in the data, so the swap can be
  pushed straight back to Hevy.
- If the data is insufficient for a category, omit it rather than padding.

{PROVENANCE_RULES}"""

KNOWLEDGE_HEADING = "## Knowledge base — cited claims you may ground advice in"


class CoachError(Exception):
    """Raised when coach generation fails or is not allowed."""


class ExerciseSwap(BaseModel):
    """A concrete exercise substitution proposal."""

    from_exercise: str
    to_exercise: str
    reason: str


class CoachFinding(BaseModel):
    """One grounded observation + recommendation."""

    category: Literal[
        "plateau",
        "imbalance",
        "recovery",
        "progression",
        "alternative",
        "consistency",
    ]
    title: str
    evidence: str = Field(description="Exact numbers/dates from the data")
    recommendation: str
    provenance: Provenance = Field(
        default="general-knowledge",
        description=(
            "'cited' only if backed by a supplied Knowledge-base claim "
            "(then fill claim_link); else 'general-knowledge'."
        ),
    )
    claim_link: str | None = Field(
        default=None,
        description="The [[id#^claim-xx]] link when provenance is 'cited'.",
    )
    swap: ExerciseSwap | None = None


class CoachReport(BaseModel):
    """Full structured coach output."""

    summary: str
    findings: list[CoachFinding]


def render_knowledge_pack(claims: Sequence[Claim]) -> str:
    """Render cited claims as a knowledge section for the coach context.

    Each line is ``- [evidence] CLAIM_TYPE text [[id#^claim-xx]]``. With no
    claims, the section instructs the coach to flag a corpus gap rather than
    pass general knowledge off as cited.
    """
    lines = [KNOWLEDGE_HEADING]
    if not claims:
        lines.append(
            "\n_No cited claims available for this topic. Label any "
            "training-science advice `general-knowledge` and flag the corpus "
            "gap — do not invent a citation._"
        )
        return "\n".join(lines)
    lines.append(
        "\nGround training-science advice in these where they apply, and "
        "reuse the exact `[[id#^claim-xx]]` link in `claim_link`:"
    )
    for claim in claims:
        prefix = f"{claim.claim_type} " if claim.claim_type else ""
        tag = f"[{claim.evidence}] " if claim.evidence else ""
        lines.append(f"- {tag}{prefix}{claim.text} {claim.link}")
    return "\n".join(lines)


def build_context(
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    today: date,
    templates: dict[str, dict[str, Any]] | None = None,
    overrides: dict[str, str] | None = None,
    plateau_weeks: int = 4,
    knowledge: Sequence[Claim] | None = None,
) -> str:
    """Build the markdown data context handed to the coach model."""
    agg = stats.compute_aggregates(records, today)
    recent = stats.records_in_range(
        records, today - timedelta(days=28), today + timedelta(days=1)
    )
    volumes = patterns.volume_by_group(recent, templates, overrides)
    ratio = patterns.push_pull_ratio(volumes)
    plateaus = patterns.detect_plateaus(histories, today, plateau_weeks)
    overload = patterns.weekly_overload(records, today)
    prs = recent_prs(histories, limit=10)

    lines = [f"# Training data as of {today.isoformat()}"]
    lines.append(
        f"\n## Overview\n- {agg['total_workouts']} total workouts, "
        f"{agg['week_count']} in the last 7 days, "
        f"{agg['month_count']} this month\n"
        f"- Volume: {agg['volume_week_kg']:,.0f} kg last 7 days, "
        f"{agg['volume_month_kg']:,.0f} kg this month\n"
        f"- Streak: {agg['current_streak_days']} days "
        f"(longest {agg['longest_streak_days']})"
    )

    lines.append("\n## Muscle group volume, last 28 days")
    for group, volume in volumes.items():
        lines.append(f"- {group}: {volume:,.0f} kg")
    if ratio is not None:
        lines.append(f"- push/pull ratio: {ratio:.2f}")

    if plateaus:
        lines.append(f"\n## Plateaus (no est. 1RM progress in {plateau_weeks} weeks)")
        for p in plateaus:
            lines.append(
                f"- {p['exercise']}: best recent e1RM "
                f"{p['best_recent_e1rm_kg']:.1f} kg vs prior "
                f"{p['best_prior_e1rm_kg']:.1f} kg "
                f"({p['recent_sessions']} recent sessions)"
            )

    if overload:
        lines.append("\n## Week-over-week volume change per exercise")
        for entry in overload[:15]:
            lines.append(
                f"- {entry['exercise']}: {entry['last_week_kg']:,.0f} kg "
                f"(prior {entry['prior_week_kg']:,.0f} kg, "
                f"delta {entry['delta_kg']:+,.0f} kg)"
            )

    if prs:
        lines.append("\n## Recent PRs")
        for pr in prs:
            lines.append(
                f"- {pr['date'].isoformat()}: {pr['exercise']} {pr['type']} "
                f"{pr['value']:.1f} kg"
            )

    lines.append("\n## Recent sessions (last 10)")
    for record in list(reversed(records))[:10]:
        exercise_list = ", ".join(e["title"] for e in record["exercises"])
        lines.append(
            f"- {record['start_time'].date().isoformat()} {record['title']}: "
            f"{record['volume_kg']:,.0f} kg ({exercise_list})"
        )

    available = sorted(histories)
    if templates:
        available = sorted(
            set(available) | {t.get("title") or "" for t in templates.values()} - {""}
        )
    lines.append("\n## Available exercises (for swap recommendations)")
    lines.append(", ".join(available))

    if knowledge is not None:
        lines.append("\n" + render_knowledge_pack(knowledge))
    return "\n".join(lines)


def check_budget(meta: dict[str, Any], today: date, max_per_day: int) -> None:
    """Raise CoachError if today's coach-call budget is exhausted."""
    calls = meta.get("coach_calls", [])
    today_calls = [c for c in calls if c.startswith(today.isoformat())]
    if len(today_calls) >= max_per_day:
        msg = (
            f"Coach budget reached: {len(today_calls)}/{max_per_day} calls today. "
            "Raise [coach].max_calls_per_day in config.toml to override."
        )
        raise CoachError(msg)


def record_call(meta: dict[str, Any]) -> None:
    """Log a coach invocation (keeps the last 50)."""
    calls = meta.setdefault("coach_calls", [])
    calls.append(now_london().isoformat())
    meta["coach_calls"] = calls[-50:]


def generate_report(
    context: str,
    model: str = DEFAULT_MODEL,
    client: Any | None = None,
) -> CoachReport:
    """Call the Anthropic API and return a validated CoachReport.

    A pre-built client may be injected for testing; otherwise the official
    SDK client is created (reads ANTHROPIC_API_KEY from the environment).
    """
    if client is None:
        try:
            import anthropic
        except ImportError as err:
            msg = "The 'anthropic' package is required for the coach command."
            raise CoachError(msg) from err
        client = anthropic.Anthropic()

    try:
        response = client.messages.parse(
            model=model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": context}],
            output_format=CoachReport,
        )
    except Exception as err:
        msg = f"Coach API call failed: {err}"
        raise CoachError(msg) from err

    report = getattr(response, "parsed_output", None)
    if report is None:
        msg = "Coach API returned no structured output."
        raise CoachError(msg)
    return report


def render_coach_note(
    report: CoachReport, today: date, recap: str | None = None
) -> str:
    """Render a coach report as a managed vault note."""
    frontmatter = {
        "date": today.isoformat(),
        "findings": len(report.findings),
        "categories": sorted({f.category for f in report.findings}),
        "tags": ["hevy/coach"],
    }
    lines = [f"# Coach Recommendations — {today.isoformat()}"]
    lines.append(f"\n{report.summary}")
    if recap:
        lines.append(f"\n{recap}")
    for finding in report.findings:
        lines.append(f"\n## {finding.title}")
        lines.append(f"*Category: {finding.category}*")
        lines.append(f"\n**Evidence:** {finding.evidence}")
        lines.append(f"\n**Recommendation:** {finding.recommendation}")
        if finding.provenance == "cited" and finding.claim_link:
            lines.append(f"\n**Grounding:** cited — {finding.claim_link}")
        else:
            lines.append("\n**Grounding:** general-knowledge")
        if finding.swap:
            lines.append(
                f"\n> [!tip] Swap **{finding.swap.from_exercise}** → "
                f"**{finding.swap.to_exercise}**\n> {finding.swap.reason}"
            )
    return render_note(frontmatter, "\n".join(lines))


def coach_note_path(today: date) -> str:
    """Relative vault path for today's coach note."""
    return f"Coach/{today.isoformat()} Recommendations.md"


def briefing_note_path(today: date) -> str:
    """Relative vault path for today's free coaching briefing."""
    return f"Coach/{today.isoformat()} Briefing.md"


def render_briefing(context: str, today: date, recap: str | None = None) -> str:
    """Render a self-contained coaching briefing (no API call, no cost).

    The note bundles the coaching instructions with the computed training
    data so it can be analyzed by Claude under an existing subscription
    (Claude Code or claude.ai) instead of a metered API call. Whatever the
    coach writes below the managed marker is preserved on regeneration. An
    optional ``recap`` (coach memory) is shown up top so Claude's analysis is
    continuity-aware.
    """
    frontmatter = {
        "date": today.isoformat(),
        "status": "needs-analysis",
        "tags": ["hevy/coach/briefing"],
    }
    lines = [
        f"# Coaching Briefing — {today.isoformat()}",
        (
            "\n> [!info] Free coaching — no API key, no per-call cost.\n"
            "> Open this note in Claude Code (or paste it into claude.ai) and "
            'ask: *"Act as the coach described below and analyze my training '
            'data."* Write the recommendations **below** the '
            "`%% hevy-brain:end %%` marker — they will survive future syncs.\n"
            ">\n"
            "> **Label every training-science point** in your write-up: append "
            "`[cited: [[id#^claim-xx]]]` when it is backed by a Knowledge-base "
            "claim below, or `[general-knowledge]` when it is not. Never label "
            "general knowledge as cited."
        ),
    ]
    if recap:
        lines.append(f"\n{recap}")
    lines.extend(
        [
            "\n## Coach instructions",
            f"\n{SYSTEM_PROMPT}",
            "\n## Your training data",
            f"\n{context}",
        ]
    )
    return render_note(frontmatter, "\n".join(lines))
