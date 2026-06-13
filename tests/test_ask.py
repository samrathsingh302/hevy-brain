"""Tests for `ask`: question parsing, retrieval and the briefing (C2)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from test_knowledge import CLAIMS_INDEX, NOTE_A, NOTE_B, TOPIC_SLEEP, TOPIC_TRAINING

from hevy_brain.cli import _load_knowledge_for_question
from hevy_brain.coach.ask import (
    ask_note_path,
    question_pattern,
    question_slug,
    question_terms,
    render_ask_briefing,
)
from hevy_brain.config import Config

TODAY = date(2026, 6, 13)


# -- question parsing -------------------------------------------------------


def test_question_terms_drops_stopwords_and_dedupes() -> None:
    terms = question_terms("How should I get my bench bench moving again?")
    assert terms == ["bench", "moving"]


def test_question_terms_keeps_short_training_words() -> None:
    assert "rpe" in question_terms("Is my RPE too high?")


def test_question_pattern_escapes_terms() -> None:
    assert question_pattern(["bench", "e1rm+"]) == "bench|e1rm\\+"
    assert question_pattern([]) is None


def test_question_slug_truncates_at_word_boundary() -> None:
    slug = question_slug(
        "How do I restructure my whole programme after a really long break?"
    )
    assert len(slug) <= 40
    assert slug.startswith("how do i restructure")
    assert not slug.endswith(" ")


def test_question_slug_falls_back_for_empty_input() -> None:
    assert question_slug("???") == "question"


def test_question_slug_cuts_a_single_overlong_word() -> None:
    # A 100+ char first word must not produce an unbounded filename
    # (verifier finding 13/06/2026: WinError 123 crash).
    assert len(question_slug("supercalifragilistic" * 10)) <= 40


def test_ask_note_path_is_dated_slugged_and_digested() -> None:
    path = ask_note_path(TODAY, "Should I deload?")
    assert re.fullmatch(
        r"Coach/2026-06-13 Ask — should i deload \([0-9a-f]{6}\)\.md", path
    )


def test_ask_note_path_reused_for_the_same_question() -> None:
    # Case/punctuation variants of one question hit the same note...
    assert ask_note_path(TODAY, "Should I deload?") == ask_note_path(
        TODAY, "should i DELOAD"
    )


def test_ask_note_path_differs_when_slugs_collide() -> None:
    # ...but different questions sharing a 40-char prefix do NOT share a note
    # (the preserved answer must never rebind to a different question).
    base = "How do I restructure my whole programme"
    path_a = ask_note_path(TODAY, f"{base} after a really long break?")
    path_b = ask_note_path(TODAY, f"{base} when travelling for work?")
    assert question_slug(f"{base} after a really long break?") == question_slug(
        f"{base} when travelling for work?"
    )
    assert path_a != path_b


# -- briefing rendering -----------------------------------------------------


def test_render_ask_briefing_bundles_question_and_context() -> None:
    note = render_ask_briefing(
        "Should I deload?",
        "# Training data\n- 285 workouts",
        TODAY,
        retrieval="topics: training · 3 claims",
    )
    assert "question: Should I deload?" in note
    assert "> Should I deload?" in note
    assert "*Knowledge retrieval: topics: training · 3 claims*" in note
    assert "Answer THE question asked" in note
    assert "Provenance (mandatory honesty rule)" in note
    assert "- 285 workouts" in note
    assert "hevy/coach/ask" in note


# -- question-driven retrieval ----------------------------------------------


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """A config whose knowledge root holds the miniature knowledge layer."""
    (tmp_path / "topics").mkdir()
    (tmp_path / "notes").mkdir()
    (tmp_path / "_meta").mkdir()
    (tmp_path / "topics" / "training.md").write_text(TOPIC_TRAINING, encoding="utf-8")
    (tmp_path / "topics" / "sleep.md").write_text(TOPIC_SLEEP, encoding="utf-8")
    (tmp_path / "notes" / "noteA.md").write_text(NOTE_A, encoding="utf-8")
    (tmp_path / "notes" / "noteB.md").write_text(NOTE_B, encoding="utf-8")
    (tmp_path / "_meta" / "claims-index.md").write_text(CLAIMS_INDEX, encoding="utf-8")
    return Config(base_dir=tmp_path, vault_path=tmp_path, data_dir=tmp_path / "data")


def test_topic_named_in_question_is_retrieved(config: Config) -> None:
    claims, summary = _load_knowledge_for_question(
        config, "How should I train around poor sleep?"
    )
    assert any(c.anchor == "claim-30" for c in claims)
    assert "topics: sleep" in summary
    assert summary.endswith("claims")


def test_terms_fall_through_to_index_and_grep(config: Config) -> None:
    claims, summary = _load_knowledge_for_question(
        config, "Are morning daylight habits worth it?"
    )
    assert [c.anchor for c in claims] == ["claim-30"]
    assert "pattern via" in summary


def test_topic_and_pattern_results_are_deduped(config: Config) -> None:
    claims, _ = _load_knowledge_for_question(
        config, "Does sleep improve with morning daylight?"
    )
    keys = [(c.source_id, c.anchor) for c in claims]
    assert len(keys) == len(set(keys))
    assert ("noteB", "claim-30") in keys


def test_unmatched_question_falls_back_to_config_topics(config: Config) -> None:
    claims, summary = _load_knowledge_for_question(config, "Qqqq zzzz?")
    assert claims  # the training topic pack
    assert "fallback topics: training" in summary


def test_missing_knowledge_layer_reports_corpus_gap(tmp_path: Path) -> None:
    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "nowhere",
        data_dir=tmp_path / "data",
    )
    claims, summary = _load_knowledge_for_question(config, "Should I deload?")
    assert claims == []
    assert "corpus gap" in summary
    assert "0 claims" in summary


def test_aborted_retrieval_is_flagged_in_the_summary(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hevy_brain.knowledge import KnowledgeAccessError, KnowledgeBase

    def _boom(self: KnowledgeBase) -> list[str]:
        raise KnowledgeAccessError("locked")

    monkeypatch.setattr(KnowledgeBase, "available_topics", _boom)

    claims, summary = _load_knowledge_for_question(config, "Should I deload?")

    assert claims == []
    assert "retrieval aborted early" in summary


# -- the command ------------------------------------------------------------


def _write_config_and_cache(tmp_path: Path, raw_workouts: dict) -> Path:
    import json

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "workouts.json").write_text(json.dumps(raw_workouts), encoding="utf-8")
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f"[vault]\npath = '{tmp_path}'\nsubfolder = \"Hevy\"\n"
        f"[sync]\ndata_dir = '{data_dir}'\n",
        encoding="utf-8",
    )
    return config_file


def test_cli_ask_writes_briefing_and_reruns_idempotently(
    tmp_path: Path, raw_workouts: dict, capsys: pytest.CaptureFixture
) -> None:
    from hevy_brain.cli import main

    config_file = _write_config_and_cache(tmp_path, raw_workouts)
    args = ["--config", str(config_file), "ask", "Should I deload my bench?"]

    assert main(args) == 0
    out = capsys.readouterr().out
    assert "Ask briefing written" in out
    notes = list((tmp_path / "Hevy" / "Coach").glob("* Ask — *.md"))
    assert len(notes) == 1
    text = notes[0].read_text(encoding="utf-8")
    assert "Should I deload my bench?" in text
    assert "## Your training data" in text

    # Re-asking the same question reuses the note without duplicating it.
    assert main(args) == 0
    notes = list((tmp_path / "Hevy" / "Coach").glob("* Ask — *.md"))
    assert len(notes) == 1
    assert notes[0].read_text(encoding="utf-8").count("## Question") == 1


def test_cli_ask_rejects_blank_question_and_empty_cache(
    tmp_path: Path, raw_workouts: dict, capsys: pytest.CaptureFixture
) -> None:
    from hevy_brain.cli import main

    config_file = _write_config_and_cache(tmp_path, raw_workouts)
    assert main(["--config", str(config_file), "ask", "   "]) == 1
    assert "Provide a question" in capsys.readouterr().err

    empty = tmp_path / "empty"
    empty.mkdir()
    empty_config = empty / "config.toml"
    empty_config.write_text(
        f"[vault]\npath = '{empty}'\nsubfolder = \"Hevy\"\n"
        f"[sync]\ndata_dir = '{empty / 'data'}'\n",
        encoding="utf-8",
    )
    assert main(["--config", str(empty_config), "ask", "Should I deload?"]) == 1
    assert "Cache is empty" in capsys.readouterr().err
