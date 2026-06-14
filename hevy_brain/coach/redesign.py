"""The `guide redesign` briefing: a programme change grounded in real data.

Same free model as the other briefings: the note bundles the redesign
instructions, the current-programme snapshot (analytics.redesign) and the
cited claims the corpus can offer, then gets analysed under an existing
Claude subscription. The redesign is written below the managed marker and
applied by editing the prepared Redesign drafts in `Routines/Drafts/`.

Honesty rule (E2 ships before E4): the knowledge corpus currently has NO
hypertrophy-programming content, so the briefing says so up front and every
programming choice must be labelled `[general-knowledge]` until programming
episodes are ingested via atlas-pipeline.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from ..knowledge import Claim
from ..vault.writer import render_note
from .advisor import PROVENANCE_RULES, render_knowledge_pack

# Drives question-style retrieval (topics + term pattern) for the briefing's
# knowledge pack. "training" matches the topic page; the rest are term signal.
REDESIGN_QUERY = (
    "training programme redesign: split, volume, sets, hypertrophy, "
    "progression, plateau, recovery"
)

REDESIGN_SYSTEM_PROMPT = f"""\
You are a strength-training coach redesigning one athlete's programme from
their real Hevy workout data. You receive a snapshot of the CURRENT programme
(split, sessions/week, weekly sets and volume per muscle group, push/pull
balance, untrained groups, plateaus, top exercises), prepared Redesign drafts
(exact copies of the current routines, ready to edit and push), and — when
available — a "Knowledge base" of cited claims distilled from sports-science
podcasts (each with an evidence tag and an `[[id#^claim-xx]]` link).

Deliverable — a programme redesign with exactly these sections:
1. **Diagnosis**: what the current programme actually is and what is wrong or
   missing — imbalances, untrained groups, plateaus, volume outliers. Every
   point grounded in the supplied numbers.
2. **Redesign**: the new split (which days, which focus) and weekly set
   targets per muscle group, with the reasoning. State plainly where a choice
   is a trade-off.
3. **Per-draft edits**: for each prepared Redesign draft, the exact
   frontmatter edits — exercises to add/remove/swap, sets, reps or rep
   ranges, loads, rest — so the athlete can apply them and push. Choose swap
   exercises ONLY from the "Available exercises" list, and note that an added
   exercise needs its `exercise_template_id` copied from a note that already
   uses it (the push parser requires the id, not just the name).
4. **What to watch**: how to tell in 3–4 weeks whether the redesign worked
   (specific numbers to compare).

Rules:
- Ground EVERY data claim in the supplied numbers and dates; never invent
  workouts, weights or dates.
- CORPUS GAP (be upfront about it): the knowledge base currently contains no
  hypertrophy-programming doctrine (set ranges, progression schemes, deloads,
  exercise selection). Label every such choice `[general-knowledge]` and say
  so once, plainly, at the top of the Redesign section.

{PROVENANCE_RULES}"""


def redesign_briefing_path(today: date) -> str:
    """Relative vault path for today's redesign briefing."""
    return f"Coach/{today.isoformat()} Redesign Briefing.md"


def _programme_lines(snapshot: dict[str, Any], today: date) -> list[str]:
    """Window, split and per-group set/volume sections of the context."""
    window = f"{snapshot['weeks']} weeks ending {snapshot['window_end'].isoformat()}"
    staleness = (today - snapshot["window_end"]).days
    lines = [
        f"\n## Training window ({window})\n"
        f"- {snapshot['sessions']} sessions "
        f"({snapshot['sessions_per_week']:.1f}/week), "
        f"{snapshot['weekly_volume_kg']:,.0f} kg/week"
    ]
    if staleness > 7:
        lines.append(
            f"- Note: the last workout was **{staleness} days ago** — this "
            "snapshot describes the programme as last run, not this week."
        )
    if snapshot["effective_weeks"] < snapshot["weeks"]:
        lines.append(
            f"- Note: logged history covers only "
            f"**{snapshot['effective_weeks']} of the {snapshot['weeks']} "
            "window weeks** — weekly rates are averaged over the covered "
            "weeks."
        )

    lines.append("\n## Split (sessions per workout, top muscle groups)")
    if snapshot["split"]:
        for entry in snapshot["split"]:
            groups = ", ".join(entry["groups"]) or "—"
            lines.append(f"- {entry['title']}: {entry['sessions']} sessions ({groups})")
    else:
        lines.append("- No sessions in the window.")

    lines.append("\n## Weekly working sets per muscle group")
    for group, sets in snapshot["weekly_sets_by_group"].items():
        volume = snapshot["volume_by_group"].get(group, 0.0)
        lines.append(f"- {group}: {sets:.1f} sets/week ({volume:,.0f} kg total)")
    if snapshot["untrained_groups"]:
        lines.append(
            "- Untrained in the window: " + ", ".join(snapshot["untrained_groups"])
        )
    if snapshot["push_pull_ratio"] is not None:
        lines.append(
            f"- push/pull ratio: {snapshot['push_pull_ratio']:.2f} "
            f"({snapshot['push_pull_flag']})"
        )
    return lines


def _exercise_lines(snapshot: dict[str, Any]) -> list[str]:
    """Plateau and top-exercise sections of the context."""
    lines: list[str] = []
    if snapshot["plateaus"]:
        lines.append("\n## Plateaus (no est. 1RM progress, window-anchored)")
        for p in snapshot["plateaus"]:
            lines.append(
                f"- {p['exercise']}: best recent e1RM "
                f"{p['best_recent_e1rm_kg']:.1f} kg vs prior "
                f"{p['best_prior_e1rm_kg']:.1f} kg "
                f"({p['recent_sessions']} recent sessions)"
            )
    if snapshot["top_exercises"]:
        lines.append("\n## Top exercises in the window")
        for entry in snapshot["top_exercises"]:
            lines.append(
                f"- {entry['title']}: {entry['sessions']} sessions, "
                f"{entry['volume_kg']:,.0f} kg, top weight "
                f"{entry['top_weight_kg']:g} kg, window e1RM "
                f"{entry['window_e1rm_kg']:.1f} kg "
                f"(all-time {entry['all_time_e1rm_kg']:.1f} kg)"
            )
    return lines


def build_redesign_context(
    snapshot: dict[str, Any],
    *,
    today: date,
    draft_paths: Sequence[str] = (),
    available: Sequence[str] = (),
    knowledge: Sequence[Claim] | None = None,
) -> str:
    """Build the markdown data context for the redesign briefing."""
    lines = [f"# Current programme as of {today.isoformat()}"]
    lines.extend(_programme_lines(snapshot, today))
    lines.extend(_exercise_lines(snapshot))

    lines.append("\n## Prepared Redesign drafts (exact copies — edit, then push)")
    if draft_paths:
        for path in draft_paths:
            lines.append(f"- [[{path}]]")
        lines.append(
            "- Apply the redesign by editing a draft's frontmatter, then "
            "`hevy-brain push routine <file> --dry-run` to preview. An "
            "unedited draft pushes nothing."
        )
    else:
        lines.append("- None written (no routines in the cache, or all skipped).")

    if available:
        lines.append("\n## Available exercises (for swap recommendations)")
        lines.append(", ".join(available))

    if knowledge is not None:
        lines.append("\n" + render_knowledge_pack(knowledge))
    return "\n".join(lines)


def render_redesign_briefing(context: str, today: date, *, retrieval: str) -> str:
    """Render the self-contained redesign briefing (no API call, no cost).

    ``retrieval`` is a one-line provenance summary of how the knowledge pack
    was assembled (matched topics / pattern / fallback / corpus gap).
    """
    frontmatter = {
        "date": today.isoformat(),
        "status": "needs-analysis",
        "tags": ["hevy/coach/briefing", "hevy/coach/redesign"],
    }
    lines = [
        f"# Redesign Briefing — {today.isoformat()}",
        (
            "\n> [!info] Free coaching — no API key, no per-call cost.\n"
            "> Open this note in Claude Code (or paste it into claude.ai) and "
            'ask: *"Act as the coach described below and redesign my '
            'programme."* Write the redesign **below** the '
            "`%% hevy-brain:end %%` marker — it will survive future syncs.\n"
            ">\n"
            "> **Label every training-science point** in your write-up: append "
            "`[cited: [[id#^claim-xx]]]` when it is backed by a Knowledge-base "
            "claim below, or `[general-knowledge]` when it is not. Never label "
            "general knowledge as cited."
        ),
        (
            "\n> [!warning] Corpus gap — programming content not ingested yet.\n"
            "> The knowledge base has no hypertrophy-programming claims (set "
            "ranges, progression, deloads), so the redesign's programming "
            "choices are `[general-knowledge]` until those episodes are "
            "ingested via atlas-pipeline."
        ),
        f"\n*Knowledge retrieval: {retrieval}*",
        "\n## Coach instructions",
        f"\n{REDESIGN_SYSTEM_PROMPT}",
        "\n## Your data",
        f"\n{context}",
    ]
    return render_note(frontmatter, "\n".join(lines))
