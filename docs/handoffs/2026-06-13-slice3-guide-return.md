---
status: done
agent: slice3-builder-1
goal: "Slice 3: E1 `guide return` — comeback protocol for the 62-day lapse"
outcome: "Shipped; 135 offline tests green (was 109), ruff clean. Live: 62-day lapse detected, Return Briefing with 214 cited claims (training+sleep), 3 Return Week 1 drafts (upper / push 1 / pull 1) in Routines/Drafts/"
gotchas: "Pushing a draft PUT-replaces the original routine in Hevy (title included) — restore = push the original loads back, which the managed note holds only until the next sync after the push. Drafts are write-once: rerunning guide return never repairs an existing draft file. Weekly baselines divide by the full window (athletes with shorter history get diluted numbers — documented semantics). Briefing date is the UTC date."
carry-on: "Live `push routine --dry-run` on a Return Week 1 draft, then E2 `guide redesign` or C2 `ask` (see prompt below)"
---

# 13/06/2026 — Slice 3: `guide return` (E1)

## Done (commits 6bb13f2 → 1286dcd, pushed)

1. **Lapse + baseline analytics** (`6bb13f2`): `analytics/comeback.py`.
   `lapse_status()` = days since last logged workout; `pre_lapse_baselines()`
   computes sessions/week, weekly volume, muscle-group split and top
   exercises (window + all-time e1RM) over the `[guide] baseline_weeks`
   window **ending at the last workout** — the lapse never dilutes the
   numbers a comeback anchors to.
2. **`guide return` command** (`b9a4a7f`):
   - `coach/comeback.py`: `build_return_context()` packs lapse facts +
     baselines + prepared-draft links + the knowledge pack;
     `render_return_briefing()` writes the free `Coach/<date> Return
     Briefing.md` with a comeback-specific prompt (week-by-week ramp,
     explicit AVOID list, recovery/sleep anchors, draft adjustments).
     Provenance rules extracted to `advisor.PROVENANCE_RULES`, shared by
     both coach prompts.
   - `vault/drafts.py`: `Return Week 1 — <routine>` drafts in
     `Routines/Drafts/`, loads at `[guide] load_fraction` (default 0.6,
     labelled `[general-knowledge]`), rounded to 2.5 kg steps, never above
     the original. Write-once; body shows original → week-1 loads + the
     PUT warning. Selection prefers routines matching pre-lapse workout
     titles, fills by recency, caps at `[guide] draft_limit`.
   - CLI: `guide return` subcommand; knowledge topics = config ∪
     {training, sleep}; `[guide]` config block (lapse_days=14,
     load_fraction=0.6, draft_limit=3, baseline_weeks=4); README + example
     config updated.
3. **Verifier fixes** (`1286dcd`) — independent fresh-eyes review
   (fix-first verdict), both bugs independently confirmed before fixing:
   - **Notes wipe (MAJOR):** drafts now carry `notes` in frontmatter — PUT
     is a full replacement, so a draft without them silently erased the
     routine's notes in Hevy.
   - **Load inversion:** `scale_weight` never exceeds the original load
     (≤2.5 kg weights pass through instead of rounding UP to 2.5).
   - Hardening: un-pushable routines filtered out of selection; duplicate
     titles get the slice-1 id-suffix scheme; `guide` dispatch branches on
     the subcommand. Real drafts were regenerated post-fix.

## Verify

`python -m pytest tests -q` → **135 passed** (was 109) · `python -m ruff
check hevy_brain tests` → clean. All offline. Live smoke against the real
cache: 62-day lapse (last workout 11/04/2026), briefing written with **214
cited claims** (training + sleep), 3 drafts parse cleanly through
`parse_routine_note` into valid PUT bodies (e.g. `upper`: 7 exercises,
14 sets).

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Drafts reuse the slice-1 PUT round-trip** (locked by the carry-on; no
  POST /routines in the client). Pushing a draft replaces the original
  routine — mitigated by write-once drafts, original loads in the body,
  the PUT warning, and `--dry-run` guidance.
- **Load fraction 0.6, configurable** — a general-knowledge default,
  explicitly NOT cited (programming corpus gap until E4); labelled as such
  in the briefing, the context and every draft.
- **Lapse threshold 14 days** (`[guide] lapse_days`); below it the command
  prints "no lapse" and writes nothing.
- **Knowledge topics for the guide = config ∪ {training, sleep}** per the
  carry-on; dedupe by (source_id, anchor).

## Watch / gotchas

- **Draft push replaces the routine in Hevy, including the title** (it
  becomes "Return Week 1 — …"). Restore path: push the original loads back
  — the managed `Routines/` note holds them until the first sync AFTER the
  push, so duplicate it into Drafts/ before pushing if you want a
  guaranteed restore file.
- **Write-once drafts:** rerunning `guide return` skips existing draft
  files (they're user-owned); a broken/stale draft must be deleted by hand
  to be regenerated.
- **Weekly baselines divide by the full configured window** even when the
  pre-lapse history is shorter — documented fixed-window semantics
  (verifier NIT, left as-is deliberately).
- The briefing embeds `PROVENANCE_RULES` written in structured-output
  field language (`provenance`/`claim_link`) while the free briefing uses
  inline labels — same pattern slice 2 shipped; honesty intent survives.
- Briefing filename uses the UTC date (can lag local by a day late at
  night — e.g. live smoke wrote `2026-06-12 Return Briefing.md`).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice3-guide-return.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. First: **live
> verification of the write path** — pick one `Routines/Drafts/Return Week
> 1 — *.md` draft, run `hevy-brain push routine <file> --dry-run`, review
> the diff, and (with Samrath's go) do the first real PUT, then `full` to
> confirm the round-trip; note the restore caveat (managed note holds the
> original spec only until the post-push sync). Then build the next slice —
> recommended: **C2 `hevy-brain ask "…"`** (question-specific briefing pack;
> small, generalises E1) or **E2 `guide redesign`** (works day one with
> honesty labels; corpus-grounded only after E4 ingestion, which is an
> atlas-pipeline task, not this repo). Offline tests with fixtures, ruff
> clean, one slice, commit per coherent step, push at end, update HANDOFF +
> dated handoff + carry-on. Last commit: see HANDOFF. Locked: explicit-push
> fence; free tiers; read-only knowledge bridge (never write pipeline
> folders, never read sources/); repo private until key rotation. Do not
> re-litigate.
