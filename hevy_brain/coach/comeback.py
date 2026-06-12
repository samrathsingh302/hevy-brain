"""The `guide return` briefing: a comeback protocol grounded in real data.

Packs the lapse facts and pre-lapse baselines (analytics.comeback) with cited
recovery/overtraining claims from the knowledge bridge into a free briefing —
same model as the weekly coach briefing: no API call, analysed under an
existing Claude subscription, recommendations written below the managed
marker where they survive regeneration.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from ..knowledge import Claim
from ..vault.writer import render_note
from .advisor import PROVENANCE_RULES, render_knowledge_pack

RETURN_SYSTEM_PROMPT = f"""\
You are a strength-training coach guiding one athlete's return after a
training lapse. You receive the lapse facts (days off, last session), the
athlete's PRE-LAPSE baselines (weekly volume, session frequency, top sets,
estimated 1RMs), draft return-week routines already prepared, and — when
available — a "Knowledge base" of cited claims distilled from sports-science
podcasts (each with an evidence tag and an `[[id#^claim-xx]]` link).

Deliverable — a comeback protocol with exactly these sections:
1. **Week-by-week ramp** (suggest 3–4 weeks): loads/volume per week relative
   to the pre-lapse baselines, ending at full resumption. Be specific —
   percentages and example top sets computed from the supplied numbers.
2. **AVOID list**: explicit things not to do in the return window (e.g.
   testing old maxes, training to failure, ignoring sleep). Ground each in a
   cited claim where one exists.
3. **Recovery & sleep anchors**: cited guidance on recovery, overtraining
   signals and sleep that applies to the ramp.
4. **Draft routine adjustments**: review the prepared Return Week 1 drafts
   and say what (if anything) to edit before pushing.

Rules:
- Ground EVERY data claim in the supplied numbers and dates; never invent
  workouts, weights or dates.
- Ramp percentages and progression schemes are NOT in the knowledge corpus
  yet — label them `[general-knowledge]` and say so once, plainly.

{PROVENANCE_RULES}"""


def return_briefing_path(today: date) -> str:
    """Relative vault path for today's return briefing."""
    return f"Coach/{today.isoformat()} Return Briefing.md"


def build_return_context(
    lapse: dict[str, Any],
    baselines: dict[str, Any],
    *,
    today: date,
    load_fraction: float,
    draft_paths: Sequence[str] = (),
    knowledge: Sequence[Claim] | None = None,
) -> str:
    """Build the markdown data context for the return briefing."""
    lines = [f"# Return-from-lapse data as of {today.isoformat()}"]
    lines.append(
        f"\n## The lapse\n- Last logged workout: "
        f"{lapse['last_workout_date'].isoformat()} "
        f"('{lapse['last_workout_title']}') — **{lapse['days_since']} days ago**"
    )

    lines.append(
        f"\n## Pre-lapse baselines ({baselines['weeks']} weeks ending "
        f"{baselines['window_end'].isoformat()})"
    )
    lines.append(
        f"- {baselines['sessions']} sessions "
        f"({baselines['sessions_per_week']:.1f}/week), "
        f"{baselines['weekly_volume_kg']:,.0f} kg/week "
        f"({baselines['volume_kg']:,.0f} kg total)"
    )
    if baselines["volume_by_group"]:
        groups = ", ".join(
            f"{group} {volume:,.0f} kg"
            for group, volume in baselines["volume_by_group"].items()
        )
        lines.append(f"- Volume by muscle group: {groups}")

    if baselines["top_exercises"]:
        lines.append("\n## Top exercises in the pre-lapse window")
        for entry in baselines["top_exercises"]:
            lines.append(
                f"- {entry['title']}: {entry['sessions']} sessions, "
                f"{entry['volume_kg']:,.0f} kg, top weight "
                f"{entry['top_weight_kg']:g} kg, window e1RM "
                f"{entry['window_e1rm_kg']:.1f} kg "
                f"(all-time {entry['all_time_e1rm_kg']:.1f} kg)"
            )

    lines.append(
        f"\n## Prepared Return Week 1 drafts (loads at {load_fraction:.0%} "
        "of pre-lapse — a configurable default, `[general-knowledge]`)"
    )
    if draft_paths:
        for path in draft_paths:
            lines.append(f"- [[{path}]]")
        lines.append(
            "- Push flow: edit the draft frontmatter if needed, then "
            "`hevy-brain push routine <file> --dry-run` to preview."
        )
    else:
        lines.append("- None written (no routines in the cache, or all skipped).")

    if knowledge is not None:
        lines.append("\n" + render_knowledge_pack(knowledge))
    return "\n".join(lines)


def render_return_briefing(context: str, today: date) -> str:
    """Render the self-contained return briefing (no API call, no cost)."""
    frontmatter = {
        "date": today.isoformat(),
        "status": "needs-analysis",
        "tags": ["hevy/coach/briefing", "hevy/coach/return"],
    }
    lines = [
        f"# Return Briefing — {today.isoformat()}",
        (
            "\n> [!info] Free coaching — no API key, no per-call cost.\n"
            "> Open this note in Claude Code (or paste it into claude.ai) and "
            'ask: *"Act as the coach described below and write my comeback '
            'protocol."* Write it **below** the `%% hevy-brain:end %%` marker '
            "— it will survive future syncs.\n"
            ">\n"
            "> **Label every training-science point** in your write-up: append "
            "`[cited: [[id#^claim-xx]]]` when it is backed by a Knowledge-base "
            "claim below, or `[general-knowledge]` when it is not. Never label "
            "general knowledge as cited."
        ),
        "\n## Coach instructions",
        f"\n{RETURN_SYSTEM_PROMPT}",
        "\n## Your data",
        f"\n{context}",
    ]
    return render_note(frontmatter, "\n".join(lines))
