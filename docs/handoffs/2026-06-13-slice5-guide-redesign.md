---
status: done
agent: slice5-builder-1
goal: "Slice 5: E2 `hevy-brain guide redesign` — programme-change briefing + editable drafts"
outcome: "guide redesign shipped: lapse-proof snapshot (split/sets/imbalance/plateaus), honesty-labelled briefing with 88 cited claims live, exact-copy Redesign drafts whose unedited push is a verified live no-op; half-open rep-range parser fix; 187 offline tests green (was 161), ruff clean"
gotchas: "Hevy rep_range can be half-open ({start: 8, end: null} = '8+ reps' — live on push 1); the parser keeps the null end verbatim, never invent an end. Redesign drafts keep the ORIGINAL title — only return-week drafts rename. weekly_sets_by_group excludes type: warmup sets. Weekly rates divide by covered weeks when history is shorter than the window."
carry-on: "F3 `push workout --update` (small, completes write-back trio) or A1 charts / C1 coach memory; E4 ingestion stays an atlas-pipeline task"
---

# 13/06/2026 — Slice 5: `guide redesign` (E2)

## Done (commits f17257a + f05704d, pushed)

1. **Env checks** (carry-on items): `HevyBrain Sync` healthy (ran 01:38
   today, exit 0x0, clean log); `HevyBrain Coach` has never fired —
   **expected**, first slot is Sunday 14/06 19:00 (0x41303 = not yet run,
   not drift). `pip install -e ".[dev]"` re-run — the `hevy-brain.exe`
   shim works again.
2. **`analytics/redesign.py`** — `training_snapshot` builds on
   `pre_lapse_baselines` (window ends at the LAST workout, so the 63-day
   lapse can't blank it) and adds: split summary (sessions + top muscle
   groups per workout title), weekly **working** sets per muscle group
   (warm-up sets excluded — verifier MAJOR), push/pull flag against the
   `[analytics]` band, untrained standard groups, and plateaus anchored at
   the window end (anchored at today they'd vanish behind the lapse).
   Weekly rates divide by *covered* weeks when history is shorter than the
   window, and the briefing says so.
3. **Redesign drafts** (`vault/drafts.py`) — write-once
   `Drafts/Redesign — <title>.md`, an **exact copy** of the routine
   (original title, original loads): the draft is an editing canvas, and
   pushing it unedited is a no-op by construction —
   `routine_diff(routine, parsed) == []` pinned across notes, rep ranges,
   supersets, rest and typeless sets. Shared `_generate_drafts` loop with
   the return drafts (behaviour unchanged, pinned by the old tests).
4. **Briefing** (`coach/redesign.py`) — `Coach/<date> Redesign
   Briefing.md`: corpus-gap warning callout up front (no programming
   claims until E4 — atlas-pipeline's job), question-style retrieval via
   `REDESIGN_QUERY` with the honest one-line summary, staleness +
   short-history notes, snapshot sections, drafts, available exercises
   (with the instruction that added exercises need an
   `exercise_template_id` copied from an existing note), provenance rules.
5. **CLI/config**: `guide redesign` subcommand; `[guide] redesign_weeks`
   (default 8); explicit dispatch (no fall-through for future guide
   subcommands).
6. **Pre-commit verifier (fix-first verdict, all fixed):** warm-ups
   counted as "working sets" (MAJOR — the metric the slice exists to
   report); weekly-rate dilution on short history; `title: null` template
   crash in the available-exercises set (fixed in redesign CLI *and* the
   pre-existing copy in `advisor.build_context`); set specs now default
   `type: normal` so typeless API sets keep the no-op exact; missing
   `routine_diff == []` assertion added.
7. **Live verification + real fallout fix (`f05704d`):** first dry-run of
   the unedited `Redesign — push 1` draft **failed to parse**: the live
   routine has `rep_range: {start: 8, end: null}` ("8+ reps"), which the
   parser rejected — meaning the documented duplicate-and-push edit flow
   was already broken for that routine. Parser now requires only `start`
   and keeps a null `end` exactly as the API returned it
   (full-replacement fidelity); diffs and set tables render "8+"
   (was "8–None"). Re-ran live: briefing with **88 cited claims**
   (topics: training + 42 via claims-index pattern), 3 drafts, and both
   `push 1` and `Return Week 1 — upper` dry-run **"no changes"** against
   the real server. Vault rebuilt (5 routine notes picked up the "8+"
   rendering).

## Verify

`python -m pytest tests -q` → **187 passed** (was 161) · `python -m ruff
check hevy_brain tests` → clean. All offline. Live: `guide redesign` run
against the real cache; two unedited drafts dry-run clean (GET + diff
only, nothing sent).

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Redesign drafts are exact copies** (original title included) — the
  no-op-when-unedited property beats a pre-renamed draft; return-week
  drafts keep their renaming behaviour.
- **Working sets exclude `type: warmup`** only — drop sets, failure sets
  etc. still count as working sets.
- **Snapshot window 8 weeks** by default (`[guide] redesign_weeks`),
  vs 4 for return baselines — a redesign wants the broader pattern.
- **Half-open rep ranges round-trip verbatim** (null end preserved);
  rejecting or inventing an end would falsify the spec. Note: a real PUT
  carrying a half-open range hasn't been exercised yet (the no-op path
  never sends); first edited push of `push 1` should still `--dry-run`
  first as usual.

## Watch / gotchas

- **Hevy is still on the week-1 `upper` routine** (restore file:
  `Drafts/RESTORE upper (original).md`); `push 1`/`pull 1` return drafts
  remain unpushed.
- The redesign briefing's corpus-gap callout is **hardcoded** — after E4
  lands programming claims, soften it (it would then understate the
  corpus).
- `Drafts/Redesign — Return Week 1 — upper.md` exists because the live
  `upper` routine is currently *named* `Return Week 1 — upper`; after
  restoring the original title, that draft goes stale (drafts are
  user-owned — delete by hand if unwanted).
- The snapshot describes the **pre-lapse** programme (window ends 11/04);
  that's by design and the briefing labels it.

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice5-guide-redesign.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — check
> `logs\coach.log` / Get-ScheduledTaskInfo)? Then build the next slice —
> recommended: **F3 `push workout --update <id>`** (fix a logged workout
> — typo'd weight, forgotten set — from its note; small; mind that
> workout sets DO support RPE 6–10 in halves, unlike routine sets) or
> **A1 progress charts** / **C1 coach memory**. Offline tests with
> fixtures, ruff clean, one slice, commit per coherent step, push at end,
> update HANDOFF + dated handoff + carry-on. Last commit: see HANDOFF.
> Locked: explicit-push fence; free tiers; read-only knowledge bridge
> (never write pipeline folders, never read sources/); repo private until
> key rotation. Do not re-litigate.
