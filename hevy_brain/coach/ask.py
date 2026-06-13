"""The `ask` briefing: one specific question, answered from real data.

Same free model as the weekly coach and `guide return` briefings: the note
bundles the question, the coaching instructions, the computed training data
and a question-specific pack of cited claims, then gets analysed under an
existing Claude subscription — no API call, no cost. The answer is written
below the managed marker where it survives regeneration.

Knowledge retrieval is question-driven: topics named in the question are
read first, then the question's significant terms become a claims-index /
notes-grep pattern (the routing.md order). When nothing matches, the
configured base topics are the fallback so the pack is never silently empty.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from ..vault.writer import render_note
from .advisor import PROVENANCE_RULES

# Words that carry no retrieval signal in a training question. Body-part
# words stay out of this list even when common ("back") — they are signal.
_STOPWORD_TEXT = """
a about after again all also and any are based bad been before best
better between both can could data did do does down for from get gets
getting good has have how into is it its just like make me more most my
need no not now of on one or our out over should so some still than that the
don dont don't
them then there these they this time to too up want was way week weeks
well were what when where which while who why will with would you your
"""
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def question_terms(question: str) -> list[str]:
    """Significant lowercase terms from the question, in order, deduped."""
    words = re.findall(r"[a-z0-9']+", question.lower().replace("’", "'"))
    terms: list[str] = []
    for word in words:
        term = word.strip("'")
        if len(term) >= 3 and term not in _STOPWORDS and term not in terms:
            terms.append(term)
    return terms


def question_pattern(terms: list[str]) -> str | None:
    """Build a case-insensitive alternation regex over the question's terms."""
    if not terms:
        return None
    return "|".join(re.escape(term) for term in terms)


def question_slug(question: str, max_length: int = 40) -> str:
    """Build a short, filename-safe slug (truncated at a word boundary)."""
    slug = ""
    for word in re.findall(r"[a-z0-9]+", question.lower()):
        candidate = f"{slug} {word}".strip()
        if len(candidate) > max_length:
            if not slug:
                # A single word longer than the budget still gets cut.
                slug = candidate[:max_length]
            break
        slug = candidate
    return slug or "question"


def _question_digest(question: str) -> str:
    """Build a stable short digest of the question's normalised words.

    Case and punctuation changes map to the same digest; different questions
    that truncate to the same slug do not.
    """
    normalised = " ".join(re.findall(r"[a-z0-9]+", question.lower()))
    return hashlib.sha1(  # noqa: S324 — filename disambiguator, not security
        normalised.encode("utf-8")
    ).hexdigest()[:6]


def ask_note_path(today: date, question: str) -> str:
    """Relative vault path for today's ask briefing.

    The slug + digest keep different questions on the same day in different
    notes (even when the slug truncates identically); re-asking the same
    question regenerates the same note (the answer below the marker
    survives). Same parenthesised-suffix scheme as duplicate routine titles.
    """
    return (
        f"Coach/{today.isoformat()} Ask — {question_slug(question)} "
        f"({_question_digest(question)}).md"
    )


ASK_SYSTEM_PROMPT = f"""\
You are a strength-training coach answering ONE specific question from the
athlete, grounded in their real Hevy workout data. You receive the question,
computed statistics (volume, PRs, plateaus, muscle balance, week-over-week
changes), the recent training history, and — when available — a "Knowledge
base" of cited claims distilled from sports-science podcasts (each with an
evidence tag and an `[[id#^claim-xx]]` link).

Deliverable — a direct, practical answer with exactly these sections:
1. **Answer**: the decision or recommendation in 2–4 sentences.
2. **From your data**: the exact numbers and dates that support it.
3. **From the knowledge base**: the cited claims that apply. Where the corpus
   is silent on something the answer needs, say "corpus gap" plainly instead
   of papering over it.
4. **Next step in Hevy**: the concrete change (sets, reps, loads, frequency),
   editable via a draft in `Routines/Drafts/` and
   `hevy-brain push routine <file> --dry-run`.

Rules:
- Answer THE question asked — do not pad it out into a general training
  review.
- Ground EVERY data claim in the supplied numbers and dates; never invent
  workouts, weights or dates.

{PROVENANCE_RULES}"""


def render_ask_briefing(
    question: str, context: str, today: date, *, retrieval: str
) -> str:
    """Render the self-contained ask briefing (no API call, no cost).

    ``retrieval`` is a one-line provenance summary of how the knowledge pack
    was assembled (matched topics / pattern / fallback / corpus gap).
    """
    frontmatter = {
        "date": today.isoformat(),
        "question": question,
        "status": "needs-analysis",
        "tags": ["hevy/coach/briefing", "hevy/coach/ask"],
    }
    lines = [
        f"# Ask Briefing — {today.isoformat()}",
        (
            "\n> [!info] Free coaching — no API key, no per-call cost.\n"
            "> Open this note in Claude Code (or paste it into claude.ai) and "
            'ask: *"Act as the coach described below and answer my question."* '
            "Write the answer **below** the `%% hevy-brain:end %%` marker — "
            "it will survive future syncs.\n"
            ">\n"
            "> **Label every training-science point** in your write-up: append "
            "`[cited: [[id#^claim-xx]]]` when it is backed by a Knowledge-base "
            "claim below, or `[general-knowledge]` when it is not. Never label "
            "general knowledge as cited."
        ),
        "\n## Question",
        f"\n> {question}",
        f"\n*Knowledge retrieval: {retrieval}*",
        "\n## Coach instructions",
        f"\n{ASK_SYSTEM_PROMPT}",
        "\n## Your training data",
        f"\n{context}",
    ]
    return render_note(frontmatter, "\n".join(lines))
