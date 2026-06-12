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
- **Newest dated handoff:** `docs/handoffs/2026-06-13-slice3-guide-return.md`

## Current state (13/06/2026)

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
   `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Main use case:
   guidance on editing training (return-from-lapse, programme redesign)
   grounded in BOTH the Hevy data and the atlas-pipeline knowledge notes,
   plus full plan editing via the API. Build order: ~~routines sync/edit~~
   → ~~knowledge bridge~~ → ~~`guide return`~~ (all done).
1. **Live verification of the write path** (next session, first item):
   `push routine --dry-run` on a `Return Week 1` draft, review the diff,
   first real PUT with Samrath's go, `full` to confirm the round-trip.
2. **Next slice** (carry-on prompt in the newest dated handoff): C2
   `hevy-brain ask "…"` (small, generalises E1) or E2 `guide redesign`
   (honesty-labelled until E4 ingestion lands in atlas-pipeline).
3. Optional: open `Hevy/Coach/2026-06-12 Return Briefing.md` in Claude and
   ask it to write the comeback protocol; output goes below the
   `%% hevy-brain:end %%` marker.

## Key facts

- Commands: `hevy-brain full | sync | vault | coach [--api] | guide return |
  status | push workout|routine|measurement …` — reads automatic, **writes to
  Hevy only via explicit `push`**. Routine edits: duplicate the note into
  `Routines/Drafts/`, edit the frontmatter, `push routine <file>` (managed
  notes regenerate hourly — don't edit in place).
- Config: `config.toml` (local, untracked — copy from `config.example.toml`).
  Secrets only in env vars `HEVY_API_KEY` / `ANTHROPIC_API_KEY`. `[knowledge]`
  block tunes the read-only bridge (`path` defaults to vault root; `topics`
  defaults to `["training"]`) — coach grounds advice in those cited claims.
- Cache: `data/` JSON (gitignored) is the source of truth; vault rebuildable
  offline from it. First sync = full backfill; then `/workouts/events` cursor.
- Safety: path-jailed atomic vault writes · user edits below
  `%% hevy-brain:end %%` preserved · deleted workouts archived, never
  destroyed · tests never touch the real account · knowledge bridge is
  read-only and refuses `sources/` (never writes pipeline folders).
- Verify: `pip install -e ".[dev]"` then `python -m pytest tests -q`
  (135 passed) + `python -m ruff check hevy_brain tests`.
