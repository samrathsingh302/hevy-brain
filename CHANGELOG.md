# Changelog

Newest first. Dates dd/mm/yyyy.

## 15/06/2026 — overnight autonomous build: 6 feature slices
Six slices shipped to main overnight (baseline 338 tests @ `1b6aa17`; end state
**444 tests pass**, ruff + mypy clean, 47 source files). Each two-pass verified
(Opus verifier SHIP). Codex primary ran for S1/S2 only — it hit its usage limit
mid-run, so S3–S6 carry Codex-verification debt to re-run on/after 17/06. Full
detail: `docs/handoffs/2026-06-15-overnight-autonomous.md`.
- **S1 — per-lift progression targets** (`971f2f6` + `69cf43c`): new
  `analytics/progression.py`; each exercise note gains an evergreen
  `> [!tip] Next session target` (double-progression off the most recent
  session's best set, bodyweight-only lifts skipped). New `[progression]` config
  block.
- **S2 — consistency heatmap** (`9c1ddc6`): new `vault/heatmap.py`; a GitHub-
  style 26-week training heatmap on the Dashboard (working-set-count metric,
  lapses read as blank). New `[charts]` heatmap fields.
- **S3 — `export --csv`** (`47bc97c`): new `export.py` +
  `hevy-brain export --csv [--out PATH] [--kind workouts|sets]` exports the cache
  to CSV for external analysis. `exports/` added to `.gitignore`.
- **S4 — `diff`** (`109029e` + `a555e2d`): new `analytics/sessiondiff.py` +
  `hevy-brain diff [exercise]` — objective last-vs-prior session comparison
  (overall or per-exercise), cp1252-safe CLI output.
- **S5 — deload-readiness flag** (`49506b0` + `37ac636`): new
  `analytics/deload.py`; a Dashboard `> [!note] Deload readiness` callout that
  fires only on deterministic thresholds (consecutive trained weeks + 14-day
  recency + plateau/high-RPE), explicitly labelled a general training-science
  heuristic, silent on a lapse. New `[analytics]` deload fields.
- **S6 — volume-landmark / MEV check** (`6bd38ac` + `622f08f`): new
  `analytics/landmarks.py`; a Dashboard table comparing recent weekly working-
  sets-per-muscle-group vs user-configurable MEV/MAV/MRV bands, general-knowledge
  labelled, honest "no recent training" degrade on a lapse. New `[landmarks]`
  config block.

## 14/06/2026 — afternoon: ruff format the tree (cosmetic close-out)
- **`ruff format hevy_brain tests`** — 28 files reformatted, committed standalone
  (`1090c3c`). Pure cosmetic drift (pre-commit ships ruff-format but the tree was
  never formatted; CI gates `ruff check` only, so main was GREEN either way).
  Verified inert: 338 offline tests pass, ruff + mypy clean, a fresh Opus verifier
  proved the AST byte-for-byte identical to HEAD across all 28 files; `cli --help`
  smoke exit 0. Codex primary pass unavailable (usage limit) — debt logged
  (`codex review --commit 1090c3c`).
- `HevyBrain Coach` debut (Sun 19:00) had not fired at session time (17:51) — task
  correctly armed; first-fire verification deferred to the next session.

## 14/06/2026 — morning: audit branch merged + coach-billing hardening (A1/A2)
- **Overnight audit branch `overnight-audit-2026-06-14` reviewed and merged to
  main.** Re-verified GREEN before merge: 338 offline tests, ruff + mypy clean,
  free-coach runtime smoke exit 0. Both verify passes clean — Codex (primary)
  "changes consistent"; fresh Opus verifier SHIP.
- **A2 (coach graceful failure):** a disk/IO error during the coach save now
  prints "Coach failed" and returns 1 instead of a raw traceback — on BOTH the
  free path and the metered `--api` path (`except (CoachError, OSError)`).
  `VaultPathError` (path-jail) stays uncaught — a safety stop, not IO. +2
  regression tests pinning that the old code tracebacked.
- **A1 (coach `--api` budget):** documented as a best-effort SOFT cap (Anthropic
  bills server-side before the local count saves), not hardened — bounded +
  inherent for this single-user CLI (your accepted call).
- **Hygiene:** gitignore the untracked Claude Code local-settings file (Codex P3)
  + `.mypy_cache`.
- Pipeline alive: hourly sync ran 15:25 (exit 0), cache 0.1h fresh; `HevyBrain
  Coach` first scheduled fire tonight 19:00 confirmed wired to the free path.
- **Parked (your call):** repo-wide `ruff format` drift (28 files — pre-commit
  ships ruff-format but the tree was never formatted; CI gates `ruff check`, so
  green); audit D1 (`config.toml` in history — pre-flip); `_shared-context`
  AUDIT_LOG reconcile (cross-repo).

## 14/06/2026 — overnight audit (branch `overnight-audit-2026-06-14`, merged 14/06)
- Autonomous correctness sweep of the slice-17 pre-public hardening + the
  money/safety surfaces it certifies. Repo left GREEN (336 offline tests, ruff +
  mypy clean, runtime smoke healthy). Fixes: removed Home-Assistant fork-leftover
  scripts; README + PROMPT.md doc drift; a pre-commit ruff-hook nit; 3
  coach-budget / config regression tests. Data-loss fences + secrets/history
  verified clean; one bounded `coach --api` budget soft-cap nuance parked for
  review (resolved the next morning — see entry above). See
  `docs/handoffs/2026-06-14-overnight-audit.md`.

## 13/06/2026 — slice 4: live write path verified + `ask` (C2)
- **First real PUT to Hevy.** `push routine` live-verified end to end:
  dry-run diff → PUT (routine `upper` → `Return Week 1 — upper` at 60%
  loads, 200 OK) → `full` round-trip. The PUT initially 400'd, which
  surfaced four fixes (all live-verified after):
  - Hevy rejects `"notes": ""` and treats a *missing* key as "clear the
    notes" (PUT is full replacement — semantics confirmed empirically);
    `parse_routine_note` now omits empty notes.
  - 4xx errors surface the server's response body (the 400 was
    undebuggable without it).
  - CLI output reconfigured with `errors="replace"` — the diff preview's
    `→` crashed default cp1252 Windows consoles mid-print.
  - Routines renamed in Hevy no longer orphan their old-title note: a
    managed-note sweep archives them (user files and `Drafts/` untouched).
- New `hevy-brain ask "…"` — one question, one free briefing
  (`Coach/<date> Ask — <slug> (<digest>).md`): question-driven knowledge
  retrieval (topics named in the question, then significant terms down the
  claims-index/grep path, config-topic fallback) with an honest retrieval
  summary; full data context; shared provenance rules. Live: 223 claims.
- Fresh-eyes verifier (fix-first) caught two MAJORs pre-commit: the managed
  marker quoted in briefing callouts split `VaultWriter.write` at the
  mention (notes duplicated on every regen — latent in coach + guide
  briefings too; marker now only counts at line start), and overlong words
  defeated slug truncation (WinError crash; slugs now hard-cut + digest
  suffix so colliding slugs never rebind a preserved answer).
- 161 offline tests (was 135), ruff clean.

## 13/06/2026 — slice 3: `guide return` (comeback protocol, E1)
- New `hevy-brain guide return`: detects the lapse from the cache
  (`analytics/comeback.py` — days since last workout vs `[guide] lapse_days`),
  computes pre-lapse baselines over the window *ending at the last workout*
  (weekly volume, session frequency, muscle-group split, top exercises with
  window + all-time e1RM), and writes a free `Coach/<date> Return Briefing.md`
  with a comeback-specific coach prompt (week-by-week ramp, AVOID list,
  recovery/sleep anchors, draft adjustments).
- Briefing grounds advice via the slice-2 knowledge bridge across topics
  `training` + `sleep` (config topics are unioned in); provenance rules
  shared with the weekly coach (`PROVENANCE_RULES`). Ramp percentages are
  honestly labelled `[general-knowledge]` — programming claims are a known
  corpus gap until E4.
- `Return Week 1` routine drafts into `Routines/Drafts/` at
  `[guide] load_fraction` (default 60%) of pre-lapse loads, rounded to
  2.5 kg and never above the original; drafts are write-once (user-owned
  once created), keep the routine notes (PUT is a full replacement), show
  original → week-1 loads in the body, and round-trip through the slice-1
  `push routine` parser. Un-pushable routines are never offered; duplicate
  titles get the id-suffix scheme.
- Independent fresh-eyes review caught a notes-wipe-on-push bug and a light-
  load inversion before first real push; both fixed with pinning tests.
  135 offline tests (was 109). Live: 62-day lapse detected, briefing with
  214 cited claims, 3 drafts (`upper`, `push 1`, `pull 1`).

## 13/06/2026 — slice 2: knowledge bridge + provenance labels
- New read-only `hevy_brain/knowledge/` package (`KnowledgeBase`) implements
  the `_meta/routing.md` consumption order — topic page → claim links into
  notes → concept tags → claims-index → grep notes/ — returning cited
  `Claim`s (text + evidence tag + `[[id#^claim-xx]]` link). Reads are jailed
  under the knowledge root and refuse `sources/`; nothing is ever written.
  Silent corpus → reported as an ingestion gap, never inferred.
- Coach grounds advice in those cited claims and labels every
  training-science point `cited` (with link) or `general-knowledge`:
  enforced structurally on the API path (`CoachFinding.provenance` /
  `claim_link`), by prompt instruction on the free briefing.
- `[knowledge]` config block (`path` defaults to vault root; `topics`
  defaults to `["training"]`); coach degrades gracefully to
  general-knowledge if the layer is unreadable. 109 offline tests (was 85).

## 12/06/2026 — slice 1: routines sync + edit (+ cursor fix)
- Routines + routine folders sync into the cache (`routines.json`,
  `archived_routines.json`, `routine_folders.json`); vanished routines
  archive, never destroyed; partial fetches can't mass-archive.
- `Hevy/Routines/` vault notes — frontmatter carries the full editable spec
  so a draft copy round-trips; deleted routines' notes move to `Archive/`.
- `hevy-brain push routine <file> [--dry-run]`: parse note → GET live
  routine → human-readable diff preview → PUT full replacement; identical
  notes send nothing; routine sets reject RPE (workout-set-only API field).
- Events cursor now stamps from server timestamps (newest event /
  workout `updated_at`) instead of post-fetch `utcnow` — closes the
  fetch-to-stamp gap that could silently skip events. 85 offline tests.

## 12/06/2026 — CV-readiness overhaul
- GitHub repo renamed `HA-hevy` → `hevy-brain` (old URL redirects); description
  + topics set; remote updated. Local folder name unchanged.
- README rewritten recruiter-grade: architecture diagram, engineering notes,
  real screenshots in `assets/` (rendered from actual generated notes, no body
  data), provenance section.
- `config.toml` untracked (personal vault path stays local); added
  `config.example.toml`; safe default without config is `vault_staging/`.
- Dependencies consolidated into `pyproject.toml` (`requirements.txt` removed,
  ruff pinned); GitHub Actions bumped (checkout v6.0.3, setup-python v6.2.0),
  superseding dependabot PRs #1/#2/#5.
- HA fork leftovers removed: issue templates replaced with CLI-appropriate
  ones, stale `homeassistant` ignore dropped from dependabot.yml.
- Pre-publication git-history audit: **clean** — no secret values or personal
  data in any reachable/unreachable blob across 107 commits. One low doc
  finding folded into HANDOFF's pre-public checklist.
- `HEVY_API_KEY` persisted at User scope and verified live (earlier today);
  hourly/weekly Task Scheduler registration still pending.

## 12/06/2026 — sync correctness (audit P1)
- Events cursor rolls back if a sync fails before the cache save succeeds;
  whole meta dict (cursor, `last_sync`, `last_full_sync`, user info) rolls
  back together; meta-written-LAST save order pinned by a partial-save test.

## 11–12/06/2026 — transformation: HA integration → hevy-brain CLI
- Full `hevy_brain/` package built (api, sync, store, analytics, vault, coach,
  writeback) + CLI; 60 offline tests; CI reduced to test + lint.
- Real end-to-end sync: 285 workouts, 29 body measurements, 486 exercise
  templates; vault generated into `C:\Users\samra\Atlas\Hevy\`.
- Coach made free-by-default (briefing note); metered API behind `--api`.
- Home Assistant integration retired; HACS/hassfest CI removed.

## Pre-06/2026 — fork era
- Forked from [hudsonbrendon/HA-hevy](https://github.com/hudsonbrendon/HA-hevy)
  (Home Assistant integration). Its API client and event-sync approach were
  later ported into the CLI; upstream history retained.
