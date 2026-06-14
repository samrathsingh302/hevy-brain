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


# --- coach memory recap (C1) -------------------------------------------------


def test_render_briefing_includes_recap_when_given(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)
    context = advisor.build_context(records, histories, TODAY)

    recap = "## Since your last briefing\n- Sessions logged since: **3**"
    note = advisor.render_briefing(context, TODAY, recap=recap)
    assert "## Since your last briefing" in note
    assert "Sessions logged since: **3**" in note

    plain = advisor.render_briefing(context, TODAY)
    assert "Since your last briefing" not in plain


def test_render_coach_note_includes_recap_when_given() -> None:
    note = advisor.render_coach_note(
        _report(), TODAY, recap="## Since your last briefing\n- foo"
    )
    assert "## Since your last briefing" in note
    assert "- foo" in note


def test_cmd_coach_free_persists_focus_and_shows_recap(
    tmp_path, raw_workouts: dict
) -> None:
    from datetime import UTC, datetime

    from hevy_brain import cli
    from hevy_brain.config import Config
    from hevy_brain.store.cache import CacheStore

    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )
    store = CacheStore(config.data_dir)
    for workout in raw_workouts.values():
        store.upsert_workout(workout)
    store.save()

    today = datetime.now(tz=UTC).date()
    note_path = config.vault_root / advisor.briefing_note_path(today)

    # First run: no prior snapshot -> no recap, but a snapshot is persisted.
    assert cli._cmd_coach(config, use_api=False) == 0
    after_first = CacheStore(config.data_dir)
    assert len(after_first.meta.get("coach_focus", [])) == 1
    assert after_first.meta["coach_focus"][0]["path"] == "free"
    assert "Since your last briefing" not in note_path.read_text(encoding="utf-8")

    # Seed an older prior snapshot so the next run has new sessions to grade.
    after_first.meta["coach_focus"] = [
        {
            "taken_on": "2026-05-20",
            "path": "free",
            "sessions_last_7d": 0,
            "current_streak_days": 0,
            "push_pull_ratio": None,
            "plateau_weeks": 4,
            "plateaus": [],
        }
    ]
    after_first.save()

    assert cli._cmd_coach(config, use_api=False) == 0
    note = note_path.read_text(encoding="utf-8")
    assert "Since your last briefing" in note
    assert "Sessions logged since" in note
    assert len(CacheStore(config.data_dir).meta["coach_focus"]) == 2


def test_cmd_coach_api_persists_focus_snapshot(
    tmp_path, raw_workouts: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hevy_brain import cli
    from hevy_brain.config import Config
    from hevy_brain.store.cache import CacheStore

    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )
    store = CacheStore(config.data_dir)
    for workout in raw_workouts.values():
        store.upsert_workout(workout)
    store.save()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(advisor, "generate_report", lambda *_a, **_k: _report())

    assert cli._cmd_coach(config, use_api=True) == 0
    focus = CacheStore(config.data_dir).meta.get("coach_focus", [])
    assert len(focus) == 1
    assert focus[0]["path"] == "api"


def test_cmd_coach_api_records_billed_call_before_focus_snapshot(
    tmp_path, raw_workouts: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Slice-17 money guarantee: the billed call is persisted BEFORE the focus
    snapshot, so a failure while building/saving that snapshot can't drop the
    count and let the daily budget guard over-bill on the next run."""
    import contextlib

    from hevy_brain import cli
    from hevy_brain.coach import memory
    from hevy_brain.config import Config
    from hevy_brain.store.cache import CacheStore

    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )
    store = CacheStore(config.data_dir)
    for workout in raw_workouts.values():
        store.upsert_workout(workout)
    store.save()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(advisor, "generate_report", lambda *_a, **_k: _report())

    # Fail the focus-snapshot step AFTER the billed call is recorded + saved.
    def _boom(*_a, **_k):
        msg = "focus snapshot failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(memory, "build_focus_snapshot", _boom)

    # The snapshot failure may surface (it is not a CoachError); the point is
    # that the billed call was already durably counted before it ran.
    with contextlib.suppress(RuntimeError):
        cli._cmd_coach(config, use_api=True)

    persisted = CacheStore(config.data_dir).meta.get("coach_calls", [])
    assert len(persisted) == 1


def test_cmd_coach_api_refuses_when_budget_exhausted(
    tmp_path, raw_workouts: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The daily budget guard must refuse a metered run at the command level —
    before any billable call — once today's cap is already reached."""
    from datetime import UTC, datetime

    from hevy_brain import cli
    from hevy_brain.config import Config
    from hevy_brain.store.cache import CacheStore

    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )
    store = CacheStore(config.data_dir)
    for workout in raw_workouts.values():
        store.upsert_workout(workout)
    today = datetime.now(tz=UTC).date()
    store.meta["coach_calls"] = [
        f"{today.isoformat()}T10:00:00+00:00"
    ] * config.coach_max_calls_per_day
    store.save()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Track whether the billable call is reached; the guard must refuse first.
    billed: list[int] = []
    monkeypatch.setattr(
        advisor, "generate_report", lambda *_a, **_k: billed.append(1)
    )

    assert cli._cmd_coach(config, use_api=True) == 1
    assert not billed  # budget guard refused before any billable call


def test_cmd_coach_free_handles_save_oserror_gracefully(
    tmp_path, raw_workouts: dict, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A2 (2026-06-14 audit): a disk/IO failure while saving the free-path focus
    snapshot must log a graceful 'Coach failed' and return 1, not escape as a
    raw traceback on the unattended Sunday coach run."""
    from hevy_brain import cli
    from hevy_brain.config import Config
    from hevy_brain.store.cache import CacheStore

    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )
    store = CacheStore(config.data_dir)
    for workout in raw_workouts.values():
        store.upsert_workout(workout)
    store.save()  # real save during setup, BEFORE the failure is injected

    def _boom(self: CacheStore) -> None:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(CacheStore, "save", _boom)

    assert cli._cmd_coach(config, use_api=False) == 1
    assert "Coach failed" in capsys.readouterr().err


def test_cmd_coach_api_handles_save_oserror_gracefully(
    tmp_path, raw_workouts: dict, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A2 (2026-06-14 audit): an OSError from the durable billed-call save is
    caught by the widened `except (CoachError, OSError)` and reported as 'Coach
    failed' (return 1), not a traceback. generate_report is mocked - no real
    API hit, no real bill."""
    from hevy_brain import cli
    from hevy_brain.config import Config
    from hevy_brain.store.cache import CacheStore

    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )
    store = CacheStore(config.data_dir)
    for workout in raw_workouts.values():
        store.upsert_workout(workout)
    store.save()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(advisor, "generate_report", lambda *_a, **_k: _report())

    def _boom(self: CacheStore) -> None:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(CacheStore, "save", _boom)

    assert cli._cmd_coach(config, use_api=True) == 1
    assert "Coach failed" in capsys.readouterr().err
