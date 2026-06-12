"""Tests for the AI coach (Anthropic client mocked — no real API calls)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.coach import advisor
from hevy_brain.coach.advisor import (
    CoachError,
    CoachFinding,
    CoachReport,
    ExerciseSwap,
)
from hevy_brain.knowledge import Claim
from hevy_brain.models import build_records

TODAY = date(2026, 6, 10)


def _report() -> CoachReport:
    return CoachReport(
        summary="Solid week overall.",
        findings=[
            CoachFinding(
                category="plateau",
                title="Bench press stalled",
                evidence="e1RM 82.3 kg on 2026-06-08 vs 82.3 kg four weeks prior",
                recommendation="Drop to 5x5 at 60 kg and rebuild.",
                provenance="cited",
                claim_link="[[xJ0IBzCjEPk#^claim-05]]",
                swap=ExerciseSwap(
                    from_exercise="Bench Press (Barbell)",
                    to_exercise="Lat Pulldown (Cable)",
                    reason="Variation to break the plateau",
                ),
            )
        ],
    )


def _claims() -> list[Claim]:
    return [
        Claim(
            source_id="xJ0IBzCjEPk",
            anchor="claim-22",
            text="Don't do intense exercise late if you struggle to sleep.",
            evidence="opinion",
            claim_type="AVOID",
        )
    ]


def test_build_context_contains_grounded_numbers(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)

    context = advisor.build_context(records, histories, TODAY)

    assert "2026-06-10" in context
    assert "Bench Press (Barbell)" in context
    assert "Available exercises" in context
    assert "push/pull ratio" in context


def test_generate_report_uses_injected_client(raw_workouts: dict) -> None:
    client = MagicMock()
    client.messages.parse.return_value = SimpleNamespace(parsed_output=_report())

    report = advisor.generate_report("data", client=client)

    assert report.summary == "Solid week overall."
    kwargs = client.messages.parse.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "high"}
    assert kwargs["output_format"] is CoachReport


def test_generate_report_wraps_api_errors() -> None:
    client = MagicMock()
    client.messages.parse.side_effect = RuntimeError("api down")

    with pytest.raises(CoachError, match="api down"):
        advisor.generate_report("data", client=client)


def test_budget_guard() -> None:
    meta: dict = {}
    advisor.check_budget(meta, TODAY, max_per_day=2)

    advisor.record_call(meta)
    advisor.record_call(meta)
    # record_call stamps with the real current date; simulate today's calls.
    meta["coach_calls"] = [f"{TODAY.isoformat()}T10:00:00+00:00"] * 2

    with pytest.raises(CoachError, match="budget"):
        advisor.check_budget(meta, TODAY, max_per_day=2)
    # Other days don't count.
    meta["coach_calls"] = ["2026-06-09T10:00:00+00:00"] * 5
    advisor.check_budget(meta, TODAY, max_per_day=2)


def test_render_coach_note() -> None:
    note = advisor.render_coach_note(_report(), TODAY)

    assert "Coach Recommendations" in note
    assert "Bench press stalled" in note
    assert "Swap **Bench Press (Barbell)**" in note
    assert "tags:" in note
    # Provenance is rendered with the citation link (E5).
    assert "**Grounding:** cited — [[xJ0IBzCjEPk#^claim-05]]" in note


def test_render_coach_note_general_knowledge() -> None:
    report = CoachReport(
        summary="x",
        findings=[
            CoachFinding(
                category="recovery",
                title="Deload week",
                evidence="3 sessions last week vs 5 prior",
                recommendation="Take a lighter week.",
                # default provenance is general-knowledge, no link
            )
        ],
    )
    note = advisor.render_coach_note(report, TODAY)
    assert "**Grounding:** general-knowledge" in note
    assert "cited" not in note


def test_provenance_defaults_to_general_knowledge() -> None:
    finding = CoachFinding(
        category="recovery",
        title="t",
        evidence="e",
        recommendation="r",
    )
    assert finding.provenance == "general-knowledge"
    assert finding.claim_link is None


def test_render_knowledge_pack_lists_cited_claims() -> None:
    pack = advisor.render_knowledge_pack(_claims())

    assert advisor.KNOWLEDGE_HEADING in pack
    assert "AVOID" in pack
    assert "[opinion]" in pack
    assert "[[xJ0IBzCjEPk#^claim-22]]" in pack


def test_render_knowledge_pack_flags_corpus_gap_when_empty() -> None:
    pack = advisor.render_knowledge_pack([])

    assert advisor.KNOWLEDGE_HEADING in pack
    assert "No cited claims" in pack
    assert "general-knowledge" in pack


def test_build_context_includes_knowledge_pack(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)

    context = advisor.build_context(records, histories, TODAY, knowledge=_claims())

    assert advisor.KNOWLEDGE_HEADING in context
    assert "[[xJ0IBzCjEPk#^claim-22]]" in context


def test_build_context_omits_knowledge_when_none(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)

    context = advisor.build_context(records, histories, TODAY)

    assert advisor.KNOWLEDGE_HEADING not in context


def test_render_briefing_is_self_contained(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)
    context = advisor.build_context(records, histories, TODAY)

    note = advisor.render_briefing(context, TODAY)

    # Bundles the coaching rules and the data, with no API needed.
    assert "Coaching Briefing" in note
    assert "no API key" in note
    assert "Coach instructions" in note
    assert "Your training data" in note
    assert "Bench Press (Barbell)" in note
    assert advisor.briefing_note_path(TODAY).endswith("Briefing.md")
    # The briefing carries the provenance-labelling instruction (E5).
    assert "[general-knowledge]" in note
    assert "cited" in note


def test_briefing_with_knowledge_grounds_advice(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)
    context = advisor.build_context(records, histories, TODAY, knowledge=_claims())

    note = advisor.render_briefing(context, TODAY)

    assert advisor.KNOWLEDGE_HEADING in note
    assert "[[xJ0IBzCjEPk#^claim-22]]" in note
