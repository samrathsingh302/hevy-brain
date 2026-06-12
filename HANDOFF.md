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
- **Newest dated handoff:** `docs/handoffs/2026-06-12-2120-cv-overhaul.md`

## Current state (12/06/2026, evening)

- Build complete and verified: 60 offline tests green, ruff clean, real
  end-to-end sync done (285 workouts / 29 measurements / 486 templates),
  vault generated into `C:\Users\samra\Atlas\Hevy\`.
- Audit P1 fixed: sync meta (events cursor + timestamps + user info) rolls
  back on failed sync; meta-written-LAST save order pinned by test.
- `HEVY_API_KEY` persisted at User scope, verified live (count 285 ✓).
- CV-readiness overhaul done: repo renamed `hevy-brain`, recruiter-grade
  README + real screenshots (no body data), config.toml out of git,
  deps single-sourced in pyproject, fork leftovers purged. See CHANGELOG.

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
   plus full plan editing via the API. Verified 12/06/2026: PUT
   /v1/routines/{id} and PUT /v1/workouts/{id} exist (no DELETE; PUT =
   full replacement). Build order: routines sync/edit → knowledge bridge →
   `guide return`. D1 cursor fix folds into the first sync-adjacent slice.
1. **Register the scheduled tasks** (hourly `full` + weekly `coach`):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
   ```
2. Optional: open `Hevy/Coach/<date> Briefing.md` in Claude and ask it to act
   as the coach; recommendations go below the `%% hevy-brain:end %%` marker.
3. Known design question (future slice, behaviour unchanged): the incremental
   cursor is stamped from `utcnow` taken *after* the events fetch
   (`hevy_brain/sync.py:84-101`), so server-side events created between fetch
   and stamp could be skipped next run.

## Key facts

- Commands: `hevy-brain full | sync | vault | coach [--api] | status | push …`
  — reads automatic, **writes to Hevy only via explicit `push`**.
- Config: `config.toml` (local, untracked — copy from `config.example.toml`).
  Secrets only in env vars `HEVY_API_KEY` / `ANTHROPIC_API_KEY`.
- Cache: `data/` JSON (gitignored) is the source of truth; vault rebuildable
  offline from it. First sync = full backfill; then `/workouts/events` cursor.
- Safety: path-jailed atomic vault writes · user edits below
  `%% hevy-brain:end %%` preserved · deleted workouts archived, never
  destroyed · tests never touch the real account.
- Verify: `pip install -e ".[dev]"` then `python -m pytest tests -q`
  (60 passed) + `python -m ruff check hevy_brain tests`.
