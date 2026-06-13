# hevy-brain — Handoff (single-writer pointer)

Current state lives here; session history lives in `docs/handoffs/` (newest
entry wins on detail). Read order per CLAUDE.md.

## What this project is

`hevy-brain` is a standalone Python CLI that syncs your full
[Hevy](https://hevy.com) workout history into the Obsidian vault
(`C:\Users\samra\Atlas`, subfolder `Hevy/`), analyses training patterns,
writes free AI coaching briefings, and pushes changes back to Hevy on
explicit command. Started as a fork of hudsonbrendon/HA-hevy (Home Assistant
integration); fully refactored into this CLI — the HA code is gone.

- **Repo:** https://github.com/samrathsingh302/hevy-brain (private; renamed
  from `HA-hevy` 12/06/2026 — old URL redirects)
- **Local path:** `C:\Users\samra\Atlas\repos\HA-hevy` (folder rename =
  optional follow-up; do it between sessions, not mid-session)
- **Newest dated handoff:** `docs/handoffs/2026-06-13-slice9-year-in-review.md`

## Current state (13/06/2026)

- **Slice 9 (A2 year-in-review) shipped (`ce4d6cc`):** one
  `Reviews/<year> Year in Review.md` per calendar year of training — totals
  (sessions/volume/reps/active days/longest streak), an embedded 12-bar
  monthly-volume Mermaid chart (reuses A1's renderer; hardcoded month labels
  for byte-identical rebuilds), best month, muscle balance + push/pull,
  most-trained lifts (distinct-workout session counts), and that year's PRs
  (top 10 + "…and N more"). New `vault/yearreview.py`; wired into `build_vault`
  (one note per year with workouts, no config). `patterns.volume_by_group`
  gained a group-name tiebreak so muscle-balance order is input-independent.
  248 offline tests (was 239), ruff clean, idempotent. Built inline (no
  product fork) + **adversarial 4-lens review** (no blockers/majors; the
  top-exercise session over-count, the tiebreak, and a within-year-streak doc
  note folded in). **Live:** rebuilt 4 year notes (2023–2026), 0 other notes
  re-rendered; 2024 verified (125 sessions / 705,293 kg / longest streak 6 /
  274 PRs, all consistent). `HevyBrain Coach` still pending first fire
  (Sat 13/06; next 14/06 19:00).
- **Slice 8 (C1 coach memory) shipped (`7ae9930`):** the coach now remembers
  what the data flagged and grades how it moved. Each `coach` run persists an
  objective focus snapshot to `meta["coach_focus"]` (consistency, push/pull
  ratio, flagged plateaus + their est-1RM — no Claude prose); the next run
  re-derives those from workouts logged **after** the prior snapshot and
  renders a `## Since your last briefing` recap (plateaus
  improved/held/regressed/can't-grade, sessions + PRs since, consistency,
  push/pull movement). **Honest by construction** — it grades the objective
  *situation* the advice addressed, never Claude's free-text recs (opaque,
  below the marker); the note says so. New `coach/memory.py` (tolerant of a
  hand-edited/old-schema `meta.json` — never crashes the unattended run);
  both coach paths persist the snapshot (the **free path now saves the cache**,
  which it previously never did); grade-before-record. 239 offline tests (was
  223), ruff clean. Built via the ultracode protocol — a 3-approach **design
  panel** (all converged on grading objective signals, never prose) and an
  **adversarial 4-lens review** (no blockers/majors; robustness + coverage
  findings folded in). **Live:** free `coach` run persisted the first snapshot
  (`{path: free, sessions_last_7d: 0, plateaus: []}` — honestly reflecting the
  lapse); no recap on a first run. `HevyBrain Coach` still pending first fire
  (Sat 13/06; next 14/06 19:00) — it will now also persist a snapshot.
- **Slice 7 (A1 progress charts) shipped (`3a75d7c`):** zero-dependency
  progress charts in the vault, rendered as Mermaid `xychart-beta` (Obsidian
  renders them natively). New `vault/charts.py` adds a **12-week
  weekly-volume bar** on the Dashboard (contiguous window — untrained weeks
  are 0 bars, so a lapse reads honestly; ISO-week `W##` labels) and a
  **per-exercise est-1RM bar** over the last 10 loaded sessions
  (`best_e1rm_kg > 0` only; `mm-dd` labels, padded nearest-5 band). Both are
  **bars on purpose** (Mermaid lines can render blank under some Obsidian
  themes, and bars avoid false continuity across irregular sessions). Guards:
  non-finite points dropped (a stray NaN can't abort the build), `<2`/all-zero
  → no chart, flat series never collapses the axis, titles/labels cleaned of
  grammar-breaking chars; a `None` chart leaves no orphan heading. Config-gated
  by a new `[charts]` block (`enabled`/`volume_weeks=12`/`e1rm_points=10`);
  the monthly-review chart was deliberately cut (low value-to-clutter). 223
  offline tests (was 204), ruff clean. Built with the ultracode workflow
  protocol — a **de-risk** fan-out (caught a build-aborting `int(NaN)`
  blocker; drove ISO labels, contiguous window, bars-over-lines) and an
  **adversarial 4-lens review** (no blockers/majors survived; test-hardening
  findings folded in) before commit. **Live:** vault rebuilt (Dashboard + 85
  exercise notes), charts verified against the real account. `HevyBrain
  Coach` still pending first fire (Sat 13/06; next 14/06 19:00).
- **Slice 6 (F3 `push workout --update`) shipped (`62c0dfb` + `f77b3ac` +
  `6125239`):** completes the **write-back trio** (workout create + routine
  edit + workout fix-up). `hevy-brain push workout <file> --update
  [--dry-run]` fixes a logged workout (typo'd weight, forgotten set, missing
  RPE) from a draft of its note: GET `/v1/workouts/{id}` → diff preview →
  PUT (full replacement), no-changes short-circuit, mirrors `push routine`.
  New client methods `async_get_workout`/`async_update_workout`. Workout
  notes are now **round-trippable**: frontmatter carries `type:
  hevy-workout`, `is_private`, `description`, and the full editable
  `exercises` spec, plus a fix-up callout; `build_workout_record` carries
  `is_private` + `superset_id`. `parse_workout_note` validates **RPE 6-10 in
  halves** (workout sets support RPE; routine sets don't — shared by the
  create + update parsers) and **requires start/end times** (a
  full-replacement PUT must never reset the session to "now"). New
  `workout_diff` + `unwrap_workout` ride a **shared `_exercise_diff` loop**
  (`routine_diff` refactored onto it, behaviour identical); `_to_utc`
  normalises times so an unedited time is never a spurious diff. The id
  comes from the note's `hevy_id` (no id arg). The whole vault was rebuilt
  (285 workout notes picked up the new frontmatter). 204 offline tests (was
  187), ruff clean. **Live (read-only):** unedited note `--update
  --dry-run` = "no changes" (round-trip holds against the real server +
  first live use of the new GET endpoint); an edited Drafts copy rendered a
  correct `sets 3 → 4` / weight+RPE diff, nothing sent. **No live workout
  PUT yet** — first real edited push should still `--dry-run` first.
  `HevyBrain Coach` still pending first fire (Sat 13/06; next 14/06 19:00).
- **Slice 5 (E2 `guide redesign`) shipped (`f17257a` + `f05704d`):**
  `hevy-brain guide redesign` snapshots the current programme from the
  cache — split, weekly **working** sets per muscle group (warm-ups
  excluded), push/pull flag, untrained groups, plateaus — with the window
  anchored at the **last workout** (lapse-proof), writes a free
  `Coach/<date> Redesign Briefing.md` with an up-front corpus-gap callout
  (no programming claims until E4, an atlas-pipeline task) and 88 cited
  claims via question-style retrieval, plus write-once `Redesign — <title>`
  drafts that are exact copies (unedited push = "no changes", pinned by
  `routine_diff == []` test and verified live). Pre-commit verifier:
  warm-up inflation (MAJOR), short-history dilution, null-title crash,
  set-type normalisation, dispatch fall-through — all fixed. The live
  dry-run surfaced a real API quirk: **half-open rep ranges**
  (`{start: 8, end: null}` = "8+ reps") were rejected by the push parser,
  breaking the edit flow for `push 1` — parser now keeps a null `end`
  verbatim, tables render "8+", both unedited drafts dry-run clean against
  the real server. 187 offline tests (was 161), ruff clean. New config:
  `[guide] redesign_weeks` (default 8). Shim + scheduled tasks confirmed
  healthy this session (sync ran 01:38 exit 0; coach first fires Sun 14/06
  19:00).
- **Slice 4 (live write path + C2 `ask`) shipped (`381efa3`):** the
  **first real PUT to Hevy is done and round-trip-verified** — routine
  `upper` is now `Return Week 1 — upper` at 60% loads (restore file:
  `Routines/Drafts/RESTORE upper (original).md`; `push 1`/`pull 1` drafts
  still unpushed). The 400 it initially hit produced four live-verified
  fixes: empty `notes` omitted from PUT bodies (Hevy rejects `""`; a
  missing key CLEARS notes — confirmed empirically), 4xx errors surface
  the server body, CLI printing survives cp1252 consoles, and renamed
  routines' orphaned notes are swept to `Archive/`. New `hevy-brain ask
  "…"` writes a free question-specific briefing
  (`Coach/<date> Ask — <slug> (<digest>).md`) with question-driven cited
  claims and an honest retrieval summary (live: 223 claims). Verifier
  caught pre-commit: inline marker mentions split `VaultWriter.write`
  (notes duplicated on regen — fixed line-anchored, protects all
  briefings) and a slug-truncation crash. 161 offline tests, ruff clean.
  **Gotcha:** the `hevy-brain.exe` shim went stale (`python -m
  hevy_brain.cli` works; re-run `pip install -e ".[dev]"`).
- **Slice 3 (E1 `guide return`) shipped (`1286dcd`):** `hevy-brain guide
  return` detects the lapse from the cache, computes pre-lapse baselines
  (window ends at the last workout), writes a free `Coach/<date> Return
  Briefing.md` grounded in cited claims (topics training + sleep), and
  drops write-once `Return Week 1` drafts into `Routines/Drafts/` at 60%
  loads (configurable `[guide]` block) that round-trip through `push
  routine`. Fresh-eyes verifier caught a notes-wipe-on-push bug + a
  light-load inversion pre-push; fixed with pinning tests. 135 offline
  tests green, ruff clean. **Live-verified:** 62-day lapse detected,
  briefing with 214 cited claims, 3 drafts (`upper`, `push 1`, `pull 1`)
  parse into valid PUT bodies. **No live PUT yet** — first push must start
  with `--dry-run` (and note: pushing a draft replaces the original
  routine, title included; the managed note holds the original spec only
  until the post-push sync).
- **Slice 2 (E3 knowledge bridge + E5 provenance) shipped + pushed
  (`1634aad`):** new read-only `hevy_brain/knowledge/` package
  (`KnowledgeBase`) walks the `_meta/routing.md` order (topic page →
  claim links → concept tags → claims-index → grep notes/) and returns
  cited `Claim`s (text + evidence tag + `[[id#^claim-xx]]` link); jailed
  under the knowledge root, refuses `sources/`, never writes. Coach now
  grounds advice in those claims and labels every training-science point
  `cited` (with link) or `general-knowledge` — structurally on the API
  path (`CoachFinding.provenance`/`claim_link`), by prompt instruction on
  the free briefing. 109 offline tests green, ruff clean. **Live-verified
  (free path):** the briefing loaded **46 cited claims** from
  `topics/training.md`. Corpus gap (no programming/nutrition claims) is
  surfaced honestly, not papered over.
- **Slice 1 (routines sync + edit, F1+F2) shipped + pushed (`aebd6db`):**
  routines + folders sync into the cache, `Hevy/Routines/` notes with
  round-trippable frontmatter, `push routine <file> [--dry-run]` does
  GET → diff preview → PUT full replacement. D1 cursor fix folded in
  (cursor now stamps from server timestamps, not utcnow). **PUT not yet
  exercised against the real API** — routines land in the vault on the
  next hourly `full` run; first live push should start with `--dry-run`.
- Build complete and verified: 85 offline tests green, ruff clean, real
  end-to-end sync done (285 workouts / 29 measurements / 486 templates),
  vault generated into `C:\Users\samra\Atlas\Hevy\`.
- Audit P1 fixed: sync meta (events cursor + timestamps + user info) rolls
  back on failed sync; meta-written-LAST save order pinned by test.
- `HEVY_API_KEY` persisted at User scope, verified live (count 285 ✓).
- CV-readiness overhaul done: repo renamed `hevy-brain`, recruiter-grade
  README + real screenshots (no body data), config.toml out of git,
  deps single-sourced in pyproject, fork leftovers purged. See CHANGELOG.
- Scheduled tasks registered 12/06/2026: `HevyBrain Sync` (hourly `full`)
  + `HevyBrain Coach` (Sundays 19:00), both Ready, logs to `logs\`.
  Registered inline (script logic, not the .ps1 — `-ExecutionPolicy Bypass`
  is blocked by the permission classifier); global python imports
  `hevy_brain` ✓.

## Locked decisions (12/06/2026 batch)

- Repo stays **private for now**; flipping public is Samrath's explicit call.
- Name: **hevy-brain** (GitHub); local folder rename optional, low priority.
- README screenshots: **real data, body measurements excluded** from anything
  published.
- `pyproject.toml` is the single dependency source; ruff pinned so the lint
  badge can't rot.

## Pre-public checklist (before flipping visibility)

1. Rotate `HEVY_API_KEY` and update the User-scope env var (standing lesson:
   a key that has appeared in any chat is treated as burned).
2. History audit 12/06/2026: **clean** — no secret values or personal data in
   any blob (107 commits, unreachable objects included). Re-audit only if
   history is rewritten before the flip.
3. Close dependabot PRs #1/#2/#5 if still open (superseded on main;
   permission classifier blocked closing them from this session).
4. Then: `gh repo edit samrathsingh302/hevy-brain --visibility public`.

## Not done yet (pick up here)

0. **North star + roadmap defined 12/06/2026** — lives in the vault:
   `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Build order:
   ~~routines sync/edit~~ → ~~knowledge bridge~~ → ~~`guide return`~~ →
   ~~live write path~~ → ~~C2 `ask`~~ → ~~E2 `guide redesign`~~ →
   ~~F3 `push workout --update`~~ (write-back trio complete) →
   ~~A1 progress charts~~ → ~~C1 coach memory~~ → ~~A2 year-in-review~~ (done).
1. **Next slice** (carry-on prompt in the newest dated handoff): F4
   (exercise-history endpoint), extend C1 to guide-draft adherence (grade
   whether a pushed Return/Redesign draft was trained to its loads — needs a
   draft pushed first), or A4 session-quality patterns (time-of-day, RPE
   coverage, duration trends). E4 (ingest programming episodes) stays an
   atlas-pipeline task; E2's briefings upgrade to corpus-grounded
   automatically once claims exist.
2. Consider pushing `Return Week 1 — push 1` / `pull 1` when training
   resumes; restore `upper` via `Drafts/RESTORE upper (original).md`
   after week 1.
3. Optional: open `Hevy/Coach/2026-06-13 Redesign Briefing.md` (or the
   2026-06-12 Return Briefing) in Claude and ask it to write the
   redesign/comeback; output goes below the `%% hevy-brain:end %%` marker.

## Key facts

- Commands: `hevy-brain full | sync | vault | coach [--api] | guide
  return|redesign | ask "…" | status | push workout [--update]|routine|measurement …`
  — reads automatic, **writes to Hevy only via explicit `push`**. Routine
  edits: duplicate the note into `Routines/Drafts/`, edit the frontmatter,
  `push routine <file>`. Workout fix-ups: duplicate the workout note into
  `Workouts/Drafts/`, correct the frontmatter, `push workout <file>
  --update` (id read from `hevy_id`). Both: managed notes regenerate hourly
  — edit a draft, don't edit in place. First push of any edit: `--dry-run`.
- Config: `config.toml` (local, untracked — copy from `config.example.toml`).
  Secrets only in env vars `HEVY_API_KEY` / `ANTHROPIC_API_KEY`. `[knowledge]`
  block tunes the read-only bridge (`path` defaults to vault root; `topics`
  defaults to `["training"]`) — coach grounds advice in those cited claims.
  `[charts]` block (`enabled`/`volume_weeks`/`e1rm_points`) toggles/tunes the
  Mermaid progress charts auto-generated into the Dashboard + exercise notes.
- Cache: `data/` JSON (gitignored) is the source of truth; vault rebuildable
  offline from it. First sync = full backfill; then `/workouts/events` cursor.
- Safety: path-jailed atomic vault writes · user edits below
  `%% hevy-brain:end %%` preserved · deleted workouts archived, never
  destroyed · tests never touch the real account · knowledge bridge is
  read-only and refuses `sources/` (never writes pipeline folders).
- Verify: `pip install -e ".[dev]"` then `python -m pytest tests -q`
  (248 passed) + `python -m ruff check hevy_brain tests`.
