"""Tests for the read-only knowledge bridge (offline, fixture vault)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hevy_brain.knowledge import KnowledgeAccessError, KnowledgeBase

# A miniature knowledge layer mirroring the real vault's shapes:
# topic page paraphrases that link [[id#^claim-xx]]; notes with DO/AVOID/INFO
# bullets, evidence tags and bare ^claim anchors; a claims-index; a sources/
# folder that must never be read.

TOPIC_TRAINING = """\
---
type: topic
title: Training & Body
tags: [training]
---

# Training & Body

## Recovery & overtraining signals

- **Don't do intense exercise late** if you struggle to sleep — read your body. [opinion] [[noteA#^claim-22]]
- Reps and errors per unit time drive skill, not hours. [preliminary] [[noteA#^claim-05]] · [[noteA#^claim-06]]

## Sources
- [[noteA|How to Learn]] (Huberman) — overview.
"""

TOPIC_SLEEP = """\
---
type: topic
title: Sleep
tags: [sleep]
---

# Sleep

- Get morning daylight. [strong] [[noteB#^claim-30]]
"""

NOTE_A = """\
---
id: noteA
title: How to Learn
tags: [training, exercise-timing]
claims: 3
---

# How to Learn

## Core protocol

- DO To learn a skill faster, perform **as many repetitions per unit time as you safely can**. [preliminary] (priority: highest — "most important factor")
  WHY: reps per unit time is the driver.
  CITE: [37:33](https://example.com&t=2253s) "as many repetitions" [[noteA.transcript#^t2253|ctx]] ^claim-05

- DO Designate a **block of time** and maximise safe reps within it. [preliminary]
  DOSE: 10 minutes to an hour.
  CITE: [45:21](https://example.com&t=2721s) "block of time" [[noteA.transcript#^t2721|ctx]] ^claim-06

- AVOID Doing intense exercise late if you struggle to sleep. [opinion]
  WHY: intense exercise disrupts sleep.
  CITE: [50:00](https://example.com&t=3000s) "intense exercise" [[noteA.transcript#^t3000|ctx]] ^claim-22
"""

NOTE_B = """\
---
id: noteB
title: Sleep Note
tags: [sleep, light]
claims: 1
---

# Sleep Note

- DO Get morning daylight for **30 to 40 minutes**. [strong]
  CITE: [10:00](https://example.com&t=600s) "morning daylight" [[noteB.transcript#^t600|ctx]] ^claim-30
"""

CLAIMS_INDEX = """\
---
type: claims-index
---

# Claims index

## [[noteA|How to Learn]]
- [[noteA#^claim-05]] DO [preliminary] — Perform as many repetitions per unit time as you safely can.
- [[noteA#^claim-22]] AVOID [opinion] — Don't do intense exercise late if you struggle to sleep.

## [[noteB|Sleep Note]]
- [[noteB#^claim-30]] DO [strong] — Get morning daylight for 30 to 40 minutes.
"""


@pytest.fixture
def kb(tmp_path: Path) -> KnowledgeBase:
    """Build a fixture knowledge layer under tmp_path and return a KB."""
    (tmp_path / "topics").mkdir()
    (tmp_path / "notes").mkdir()
    (tmp_path / "_meta").mkdir()
    (tmp_path / "sources").mkdir()

    (tmp_path / "topics" / "training.md").write_text(TOPIC_TRAINING, encoding="utf-8")
    (tmp_path / "topics" / "sleep.md").write_text(TOPIC_SLEEP, encoding="utf-8")
    (tmp_path / "notes" / "noteA.md").write_text(NOTE_A, encoding="utf-8")
    (tmp_path / "notes" / "noteB.md").write_text(NOTE_B, encoding="utf-8")
    (tmp_path / "_meta" / "claims-index.md").write_text(CLAIMS_INDEX, encoding="utf-8")
    (tmp_path / "sources" / "noteA.transcript.md").write_text(
        "SECRET raw transcript text", encoding="utf-8"
    )
    return KnowledgeBase(tmp_path)


def test_available_topics(kb: KnowledgeBase) -> None:
    assert kb.available_topics() == ["sleep", "training"]


def test_read_topic_extracts_claims_with_tags_and_links(kb: KnowledgeBase) -> None:
    page = kb.read_topic("training")
    assert page is not None
    # One bullet has two links → two claims; total three claims on the page.
    assert len(page.claims) == 3
    by_anchor = {c.anchor: c for c in page.claims}
    assert set(by_anchor) == {"claim-05", "claim-06", "claim-22"}

    c22 = by_anchor["claim-22"]
    assert c22.evidence == "opinion"
    assert c22.link == "[[noteA#^claim-22]]"
    assert "intense exercise late" in c22.text
    # Evidence tag and link are stripped out of the paraphrase text.
    assert "[opinion]" not in c22.text
    assert "[[" not in c22.text


def test_read_topic_ignores_transcript_links(kb: KnowledgeBase) -> None:
    # The note links [[noteA.transcript#^t2253|ctx]] must never be parsed as
    # claim links (the "." in the id and the "t" anchor disqualify them).
    page = kb.read_topic("training")
    assert page is not None
    assert all("transcript" not in c.source_id for c in page.claims)
    assert all(c.anchor.startswith("claim-") for c in page.claims)


def test_resolve_returns_authoritative_note_text(kb: KnowledgeBase) -> None:
    claim = kb.resolve("noteA", "claim-05")
    assert claim is not None
    assert claim.claim_type == "DO"
    assert claim.evidence == "preliminary"
    # Note text is the authoritative statement, with the priority tail trimmed.
    assert "as many repetitions per unit time" in claim.text
    assert "priority" not in claim.text
    assert claim.link == "[[noteA#^claim-05]]"


def test_resolve_missing_note_or_anchor_returns_none(kb: KnowledgeBase) -> None:
    assert kb.resolve("noteA", "claim-99") is None
    assert kb.resolve("ghost", "claim-01") is None


def test_claims_for_topic_resolves_to_note_text(kb: KnowledgeBase) -> None:
    claims = kb.claims_for_topic("training", authoritative=True)
    types = {c.anchor: c.claim_type for c in claims}
    # claim-22 is AVOID in the note even though the page paraphrase has no type.
    assert types["claim-22"] == "AVOID"
    assert types["claim-05"] == "DO"


def test_claims_with_tag(kb: KnowledgeBase) -> None:
    claims = kb.claims_with_tag("training")
    assert claims  # training topic page is tagged `training`
    assert all(c.anchor.startswith("claim-") for c in claims)
    # A concept that no topic page carries but a note does still resolves.
    light = kb.claims_with_tag("light")
    assert any(c.anchor == "claim-30" for c in light)


def test_iter_index_claims(kb: KnowledgeBase) -> None:
    claims = kb.iter_index_claims()
    assert len(claims) == 3
    c30 = next(c for c in claims if c.anchor == "claim-30")
    assert c30.claim_type == "DO"
    assert c30.evidence == "strong"
    assert "morning daylight" in c30.text


def test_grep_notes(kb: KnowledgeBase) -> None:
    hits = kb.grep_notes("morning daylight")
    assert [c.anchor for c in hits] == ["claim-30"]
    assert kb.grep_notes("nonexistent phrase") == []


def test_retrieve_prefers_topic_then_falls_back(kb: KnowledgeBase) -> None:
    # Step 1: topic page answers.
    result = kb.retrieve(topic="training")
    assert result.step == "topic"
    assert not result.gap
    assert len(result.claims) == 3

    # Step 3: no topic, concept tag answers.
    result = kb.retrieve(topic="ghost", concept="light")
    assert result.step == "tag"
    assert any(c.anchor == "claim-30" for c in result.claims)

    # Step 4: claims-index answers a pattern when no topic/concept given.
    result = kb.retrieve(pattern="morning daylight")
    assert result.step == "claims-index"
    assert result.claims[0].anchor == "claim-30"


def test_retrieve_reports_gap_when_silent(kb: KnowledgeBase) -> None:
    result = kb.retrieve(topic="nutrition", concept="protein", pattern="creatine")
    assert result.gap is True
    assert result.step == "none"
    assert result.claims == ()


def test_sources_are_never_read(kb: KnowledgeBase) -> None:
    with pytest.raises(KnowledgeAccessError, match="sources"):
        kb._read("sources/noteA.transcript.md")
    # Path traversal back into sources/ is also refused.
    with pytest.raises(KnowledgeAccessError):
        kb._read("notes/../sources/noteA.transcript.md")


def test_reads_outside_root_refused(kb: KnowledgeBase) -> None:
    with pytest.raises(KnowledgeAccessError, match="outside"):
        kb._read("../escape.md")


def test_missing_topic_returns_none(kb: KnowledgeBase) -> None:
    assert kb.read_topic("does-not-exist") is None
    assert kb.claims_for_topic("does-not-exist") == []
