# Changelog

Newest first. Dates dd/mm/yyyy.

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
