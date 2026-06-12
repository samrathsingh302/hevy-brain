"""Read-only reader for the atlas-pipeline knowledge layer.

Implements the retrieval order defined in the vault's ``_meta/routing.md`` so
coach briefings can ground advice in *cited* claims rather than inventing
training science:

    1. topic page  →  2. claim links into notes  →  3. concept tags
    →  4. claims-index  →  5. grep notes/

Every claim is returned with its evidence tag (``strong`` / ``preliminary`` /
``opinion`` / ``contested``) and its block-anchored link
(``[[id#^claim-xx]]``) so the citation round-trips back to the vault.

Fences (mirroring ``routing.md`` and the project ``CLAUDE.md``):

- **Never reads ``sources/``** — raw transcripts are not a query surface.
  A path that resolves inside ``sources/`` raises ``KnowledgeAccessError``.
- **Read-only**: this module only ever reads; it never writes the vault.
- If the corpus is silent on a question, retrieval reports an ingestion
  ``gap`` instead of inferring — callers must not fabricate a citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

EVIDENCE_TAGS = ("strong", "preliminary", "opinion", "contested")
CLAIM_TYPES = ("DO", "AVOID", "INFO")

# [[id#^claim-12]] — id is alnum/_/- only, so transcript links such as
# [[id.transcript#^t1120|ctx]] (a "." in the id, a "t" anchor) never match.
_CLAIM_LINK_RE = re.compile(r"\[\[([A-Za-z0-9_-]+)#\^(claim-\d+)\]\]")
_EVIDENCE_RE = re.compile(r"\[(" + "|".join(EVIDENCE_TAGS) + r")\]")
_LIST_MARKER_RE = re.compile(r"^\s*-\s+")
_TYPE_PREFIX_RE = re.compile(r"^(" + "|".join(CLAIM_TYPES) + r")\s+")
_PRIORITY_TAIL_RE = re.compile(r"\s*\((?:priority|DOSE):.*$", re.IGNORECASE)
# A line in claims-index.md: "- [[id#^claim-01]] DO [strong] — text"
_INDEX_LINE_RE = re.compile(
    r"-\s*\[\[([A-Za-z0-9_-]+)#\^(claim-\d+)\]\]\s+(\w+)\s+\[(\w+)\]\s+[—-]\s+(.*)"
)

SOURCES_DIRNAME = "sources"


class KnowledgeAccessError(Exception):
    """Raised when a read would touch a forbidden path (e.g. ``sources/``)."""


@dataclass(frozen=True)
class Claim:
    """One cited claim from the knowledge base."""

    source_id: str
    anchor: str  # e.g. "claim-05"
    text: str
    evidence: str | None  # strong | preliminary | opinion | contested
    claim_type: str | None  # DO | AVOID | INFO (None for a topic-page paraphrase)

    @property
    def link(self) -> str:
        """The round-trippable Obsidian block link, ``[[id#^claim-xx]]``."""
        return f"[[{self.source_id}#^{self.anchor}]]"

    def labelled(self) -> str:
        """Render one line as ``[evidence] text [[id#^claim-xx]]``."""
        tag = f"[{self.evidence}] " if self.evidence else ""
        return f"{tag}{self.text} {self.link}"


@dataclass(frozen=True)
class TopicPage:
    """A parsed topic page and the claims it links."""

    name: str
    claims: tuple[Claim, ...]


@dataclass(frozen=True)
class RetrievalResult:
    """The outcome of a single retrieval, with which step answered it."""

    claims: tuple[Claim, ...]
    step: str  # "topic" | "tag" | "claims-index" | "grep" | "none"
    detail: str  # the topic/concept/pattern that produced the result
    gap: bool  # True when nothing was found — an ingestion gap, do not infer


def _clean_text(line: str) -> str:
    """Strip the list marker, claim-type prefix, evidence tags and links."""
    text = _LIST_MARKER_RE.sub("", line).strip()
    text = _TYPE_PREFIX_RE.sub("", text)
    text = _CLAIM_LINK_RE.sub("", text)
    text = _EVIDENCE_RE.sub("", text)
    text = _PRIORITY_TAIL_RE.sub("", text)
    # Collapse whitespace and tidy a trailing separator left by a removed link.
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(" ·-—").strip()


class KnowledgeBase:
    """Read-only view over the vault knowledge layer (topics/notes/_meta).

    ``root`` is the folder that contains the ``topics/``, ``notes/`` and
    ``_meta/`` directories (in this vault, the Atlas root). All reads are
    jailed under ``root`` and refused inside ``sources/``.
    """

    def __init__(
        self,
        root: Path,
        *,
        topics_dir: str = "topics",
        notes_dir: str = "notes",
        meta_dir: str = "_meta",
    ) -> None:
        """Root the knowledge base at the folder holding topics/notes/_meta."""
        self.root = Path(root).resolve()
        self.topics_dir = topics_dir
        self.notes_dir = notes_dir
        self.meta_dir = meta_dir

    # -- safety -----------------------------------------------------------

    def _safe(self, rel_path: str) -> Path:
        """Resolve ``rel_path`` under the root, refusing escapes and sources/."""
        target = (self.root / rel_path).resolve()
        if self.root != target and self.root not in target.parents:
            msg = f"Refusing to read outside the knowledge root: {rel_path!r}"
            raise KnowledgeAccessError(msg)
        rel = target.relative_to(self.root)
        if rel.parts and rel.parts[0] == SOURCES_DIRNAME:
            msg = "Refusing to read sources/ — raw transcripts are not a query surface."
            raise KnowledgeAccessError(msg)
        return target

    def _read(self, rel_path: str) -> str | None:
        target = self._safe(rel_path)
        if not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    # -- topic pages (steps 1 + 2) ---------------------------------------

    def available_topics(self) -> list[str]:
        """Topic-page stems present under ``topics/``."""
        topics_path = self._safe(self.topics_dir)
        if not topics_path.is_dir():
            return []
        return sorted(p.stem for p in topics_path.glob("*.md"))

    def read_topic(self, name: str) -> TopicPage | None:
        """Parse a topic page into its linked claims (the paraphrase layer).

        Each bullet that carries one or more ``[[id#^claim-xx]]`` links yields
        one ``Claim`` per link, sharing the bullet's text and evidence tag.
        """
        text = self._read(f"{self.topics_dir}/{name}.md")
        if text is None:
            return None
        claims: list[Claim] = []
        for line in text.splitlines():
            links = _CLAIM_LINK_RE.findall(line)
            if not links:
                continue
            evidence_match = _EVIDENCE_RE.search(line)
            evidence = evidence_match.group(1) if evidence_match else None
            paraphrase = _clean_text(line)
            for source_id, anchor in links:
                claims.append(
                    Claim(
                        source_id=source_id,
                        anchor=anchor,
                        text=paraphrase,
                        evidence=evidence,
                        claim_type=None,
                    )
                )
        return TopicPage(name=name, claims=tuple(claims))

    def resolve(self, source_id: str, anchor: str) -> Claim | None:
        """Resolve a claim link to its authoritative note text (step 2).

        Returns ``None`` if the note or the anchor is missing.
        """
        text = self._read(f"{self.notes_dir}/{source_id}.md")
        if text is None:
            return None
        lines = text.splitlines()
        anchor_token = f"^{anchor}"
        anchor_idx = next(
            (i for i, line in enumerate(lines) if anchor_token in line), None
        )
        if anchor_idx is None:
            return None
        # Walk back to the bullet's first line (the claim statement).
        start = anchor_idx
        while start > 0 and not _LIST_MARKER_RE.match(lines[start]):
            start -= 1
        first_line = lines[start]
        body = _LIST_MARKER_RE.sub("", first_line).strip()
        type_match = _TYPE_PREFIX_RE.match(body)
        claim_type = type_match.group(1) if type_match else None
        evidence_match = _EVIDENCE_RE.search(first_line)
        evidence = evidence_match.group(1) if evidence_match else None
        return Claim(
            source_id=source_id,
            anchor=anchor,
            text=_clean_text(first_line),
            evidence=evidence,
            claim_type=claim_type,
        )

    def claims_for_topic(
        self, name: str, *, authoritative: bool = True
    ) -> list[Claim]:
        """All claims a topic page links, optionally resolved to note text."""
        page = self.read_topic(name)
        if page is None:
            return []
        if not authoritative:
            return list(page.claims)
        resolved: list[Claim] = []
        for claim in page.claims:
            resolved.append(self.resolve(claim.source_id, claim.anchor) or claim)
        return resolved

    # -- concept tags (step 3) -------------------------------------------

    def _frontmatter_tags(self, text: str) -> list[str]:
        if not text.startswith("---"):
            return []
        end = text.find("\n---", 3)
        if end == -1:
            return []
        try:
            meta = yaml.safe_load(text[3:end]) or {}
        except yaml.YAMLError:
            return []
        tags = meta.get("tags", []) if isinstance(meta, dict) else []
        return [str(t) for t in tags] if isinstance(tags, list) else []

    def files_with_tag(self, concept: str) -> dict[str, list[str]]:
        """Topic stems and note ids whose frontmatter ``tags`` include concept."""
        hits: dict[str, list[str]] = {"topics": [], "notes": []}
        for kind, dirname in (("topics", self.topics_dir), ("notes", self.notes_dir)):
            base = self._safe(dirname)
            if not base.is_dir():
                continue
            for path in sorted(base.glob("*.md")):
                if concept in self._frontmatter_tags(path.read_text(encoding="utf-8")):
                    hits[kind].append(path.stem)
        return hits

    def claims_with_tag(self, concept: str) -> list[Claim]:
        """Claims from every topic page (then note) tagged with ``concept``."""
        hits = self.files_with_tag(concept)
        claims: list[Claim] = []
        for topic in hits["topics"]:
            claims.extend(self.claims_for_topic(topic))
        if claims:
            return claims
        for note_id in hits["notes"]:
            claims.extend(self._all_note_claims(note_id))
        return claims

    # -- claims-index (step 4) -------------------------------------------

    def iter_index_claims(self) -> list[Claim]:
        """Every claim listed in ``_meta/claims-index.md``."""
        text = self._read(f"{self.meta_dir}/claims-index.md")
        if text is None:
            return []
        claims: list[Claim] = []
        for line in text.splitlines():
            match = _INDEX_LINE_RE.match(line.strip())
            if not match:
                continue
            source_id, anchor, claim_type, evidence, body = match.groups()
            claims.append(
                Claim(
                    source_id=source_id,
                    anchor=anchor,
                    text=body.strip(),
                    evidence=evidence if evidence in EVIDENCE_TAGS else None,
                    claim_type=claim_type if claim_type in CLAIM_TYPES else None,
                )
            )
        return claims

    # -- grep notes/ (step 5) --------------------------------------------

    def _all_note_claims(self, source_id: str) -> list[Claim]:
        text = self._read(f"{self.notes_dir}/{source_id}.md")
        if text is None:
            return []
        claims: list[Claim] = []
        # Anchors in notes appear as bare "^claim-xx" at the end of a bullet.
        for match in re.finditer(r"\^(claim-\d+)", text):
            claim = self.resolve(source_id, match.group(1))
            if claim is not None:
                claims.append(claim)
        return claims

    def grep_notes(self, pattern: str) -> list[Claim]:
        """Claims whose statement matches ``pattern`` (case-insensitive regex)."""
        notes_path = self._safe(self.notes_dir)
        if not notes_path.is_dir():
            return []
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return []
        claims: list[Claim] = []
        for path in sorted(notes_path.glob("*.md")):
            for claim in self._all_note_claims(path.stem):
                if regex.search(claim.text):
                    claims.append(claim)
        return claims

    # -- the routing order -----------------------------------------------

    def retrieve(
        self,
        *,
        topic: str | None = None,
        concept: str | None = None,
        pattern: str | None = None,
        authoritative: bool = True,
    ) -> RetrievalResult:
        """Walk the routing.md order and return the first step that answers.

        Tries, in order: the topic page, then the concept tag, then the
        claims-index (filtered by ``pattern``), then a grep over notes/.
        Returns ``gap=True`` when nothing is found — the caller must declare
        an ingestion gap rather than infer an answer.
        """
        if topic:
            claims = self.claims_for_topic(topic, authoritative=authoritative)
            if claims:
                return RetrievalResult(tuple(claims), "topic", topic, gap=False)
        if concept:
            claims = self.claims_with_tag(concept)
            if claims:
                return RetrievalResult(tuple(claims), "tag", concept, gap=False)
        if pattern:
            index_hits = [
                c
                for c in self.iter_index_claims()
                if re.search(pattern, c.text, re.IGNORECASE)
            ]
            if index_hits:
                return RetrievalResult(
                    tuple(index_hits), "claims-index", pattern, gap=False
                )
            grep_hits = self.grep_notes(pattern)
            if grep_hits:
                return RetrievalResult(tuple(grep_hits), "grep", pattern, gap=False)
        detail = topic or concept or pattern or ""
        return RetrievalResult((), "none", detail, gap=True)
