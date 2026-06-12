---
status: done
agent: slice2-builder-1
goal: "Slice 2: E3 knowledge bridge + E5 provenance labels"
outcome: "Both shipped; 109 offline tests green (was 85), ruff clean, pushed (1634aad). Live: free briefing loaded 46 cited claims from topics/training.md"
gotchas: "Coach output is graded for honesty only at the prompt layer — the API path enforces provenance structurally (CoachFinding.provenance/claim_link), but the FREE briefing relies on Claude obeying the inline-label instruction; nothing mechanically checks a hand-written briefing's labels. Knowledge root defaults to the vault root (topics/notes/_meta are siblings of Hevy/)."
carry-on: "E1 `guide return` (see prompt below)"
---

# 13/06/2026 — Slice 2: knowledge bridge (E3) + provenance labels (E5)

## Done (commits 162ca36 → 1634aad, pushed)

1. **E3 knowledge bridge** (`162ca36`): new `hevy_brain/knowledge/` package.
   `KnowledgeBase` (reader.py) implements the `_meta/routing.md` consumption
   order as a `retrieve()` walk: topic page → claim links into notes →
   concept tag → claims-index → grep notes/. Returns frozen `Claim`s
   (`source_id`, `anchor`, `text`, `evidence`, `claim_type`, `.link`
   property = `[[id#^claim-xx]]`). Topic pages give the paraphrase layer;
   `resolve()` walks a note's bullet to the authoritative statement (DO/
   AVOID/INFO + evidence tag). `retrieve()` returns `gap=True` (step
   `none`) when the corpus is silent — caller declares an ingestion gap,
   never infers.
   - **Fences:** every read is jailed under the knowledge root and refused
     inside `sources/` (`KnowledgeAccessError`); path traversal back into
     `sources/` is also refused. Read-only — the module never writes.
   - Transcript links (`[[id.transcript#^t1120|ctx]]`) are structurally
     excluded from claim parsing (the `.` in the id and `t` anchor fail the
     `[[id#^claim-xx]]` regex). 14 fixture-vault tests.
2. **E5 provenance + grounding** (`1634aad`):
   - `advisor.render_knowledge_pack()` renders cited claims into the coach
     context under a `## Knowledge base` heading; empty corpus emits a
     "flag the gap, don't fabricate" instruction instead.
   - `build_context(..., knowledge=...)` appends the pack; `SYSTEM_PROMPT`
     carries the mandatory provenance rule (cited only if a supplied claim
     backs it, with the exact link in `claim_link`; else general-knowledge;
     never fake a citation; declare gaps).
   - `CoachFinding` gains `provenance: "cited"|"general-knowledge"` (default
     general-knowledge) + `claim_link`; `render_coach_note` renders
     **Grounding:**; the free briefing carries the inline `[cited: …]` /
     `[general-knowledge]` labelling instruction.
   - `config`: `[knowledge] path` (defaults to vault root) + `topics`
     (default `["training"]`); `Config.knowledge_root` property.
   - `cli._load_knowledge` builds the KB, dedupes claims across configured
     topics, and degrades to general-knowledge if the layer is unreadable;
     prints the cited-claim count on both coach paths.

## Verify

`python -m pytest tests -q` → **109 passed** (was 85) · `python -m ruff
check hevy_brain tests` → clean. All offline (fixture vault folders; no
real account, no API). Live smoke: `coach` (free path) against the real
vault wrote `Hevy/Coach/<date> Briefing.md` with **46 cited claims** from
`topics/training.md`, the `## Knowledge base` section, and the provenance
instruction.

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Knowledge root = vault root by default.** `topics/`, `notes/`, `_meta/`
  are siblings of the `Hevy/` subfolder, so `knowledge_root` falls back to
  `vault_path`. Overridable via `[knowledge] path`.
- **Default topic = `training`.** The coach pulls cited claims from the
  training topic page; `[knowledge] topics` takes a list (E1 will add
  `sleep` for recovery). Resolved to authoritative note text, not the page
  paraphrase, so the DO/AVOID type and evidence tag come through.
- **Authoritative-text on resolve, paraphrase as fallback.** Per routing.md
  "the note is authoritative"; if an anchor can't be resolved the topic
  paraphrase claim is kept rather than dropped.
- **Graceful degrade, never a hard fail.** A missing/unreadable knowledge
  layer logs a warning and yields zero claims — coaching still runs, all
  advice labelled general-knowledge with the corpus gap surfaced.

## Watch / gotchas

- **Free-briefing labels are prompt-enforced, not mechanically checked.**
  The API `CoachReport` enforces provenance via the schema; a hand-written
  briefing below the marker relies on Claude following the inline-label
  instruction. No validator inspects the human/Claude-authored prose.
- **Corpus gap is real.** `topics/training.md` has no hypertrophy
  programming / progression / nutrition claims (logged in `_meta/gap-log.md`
  + routing.md known-gaps). Redesign-style advice will legitimately come
  back mostly general-knowledge until E4 (atlas-pipeline ingestion) lands —
  that's the honest state, not a bug.
- `claims-index.md` parsing keys on the exact `- [[id#^claim-xx]] TYPE
  [tag] — text` line shape; the index is auto-generated so the shape is
  stable, but a format change there would silently drop the step-4 fallback
  (topic/tag steps are unaffected).

## Carry-on prompt (next slice — E1, fresh session)

> Read CLAUDE.md + HANDOFF.md, then the roadmap note
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md` (§E1) and the newest
> dated handoff. Build **slice 3: `hevy-brain guide return`** — the
> comeback-protocol command for the current 62-day lapse. (a) lapse +
> baseline analytics (detect the gap from the cache, pull pre-lapse weekly
> volume, top sets, e1RMs); (b) a `Hevy/Coach/` comeback briefing that packs
> those baselines with cited recovery/overtraining claims via the slice-2
> knowledge bridge (`KnowledgeBase.retrieve`, topics `training` + `sleep`),
> every training-science point provenance-labelled (E5 contract already
> built); (c) offer draft routines (`Return Week 1`) into `Routines/Drafts/`
> ready for `push routine` (reuse the slice-1 round-trip). Honour the corpus
> gap honestly — programming claims aren't ingested yet, so ramp guidance is
> general-knowledge with the gap surfaced. Offline tests with fixtures, ruff
> clean, one slice, commit per coherent step, push at end, update HANDOFF +
> dated handoff + carry-on. Last commit: 1634aad. Locked: explicit-push
> fence; free tiers; read-only knowledge bridge (never write pipeline
> folders, never read sources/); repo private until key rotation. Do not
> re-litigate.
