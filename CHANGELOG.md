# Changelog

Newest first. Dates dd/mm/yyyy.

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
