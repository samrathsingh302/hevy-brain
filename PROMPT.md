# Hevy → Obsidian Second Brain — Refactoring Prompt

> **How to use this:** Open Claude Code in this repo and paste everything below the divider as your first message (or run `claude "$(cat PROMPT.md)"`). Fill in the `<<PLACEHOLDERS>>` in the Configuration section first. This prompt is written for a single, fully-specified kickoff turn — Opus 4.8 performs best on long autonomous work when the entire goal, constraints, and definition of done are given up front.

---

# Mission

Transform this repository from a Home Assistant custom integration into **Hevy Second Brain**: a standalone Python application that continuously syncs all of my Hevy workout data into my Obsidian vault, analyzes my training patterns, generates AI-powered coaching insights and exercise alternatives, and can write back to Hevy on my behalf (create workouts, log body measurements) — so I rarely have to touch the Hevy app manually.

Work autonomously through all phases. For minor choices (naming, file layout details, default values, which of two equivalent approaches), pick a reasonable option and note it — do not stop to ask. Ask only for scope changes or destructive actions not already authorized here.

# Configuration (fill these in before running)

- `VAULT_PATH`: `vault_staging/` inside this repo (gitignored). The real Obsidian vault is in active use, so generate into this staging folder for now; the path is configurable in `config.toml` so it can be pointed at the real vault later.
- `VAULT_SUBFOLDER`: `Fitness/Hevy` (all generated notes live under this folder — never write outside it). **Build note:** this kickoff spec uses `Fitness/Hevy` throughout (including the tree below); the shipped tool simplified the default to `Hevy` — see `config.example.toml`, `README.md`, and `CLAUDE.md`.
- `HEVY_API_KEY`: read from env var `HEVY_API_KEY` (get it at hevy.com/settings?developer). Never hardcode it.
- `ANTHROPIC_API_KEY`: read from env var `ANTHROPIC_API_KEY` (used only by the AI coach module).
- Platform: Windows 11, Python 3.12+. Scheduling via Windows Task Scheduler (generate the registration script) — no daemons that assume Linux.

# What already exists (reuse it — do not rewrite from scratch)

This repo is a mature, well-tested HA integration for Hevy. Salvage aggressively:

- `custom_components/hevy/api.py` — **`HevyApiClient`**: aiohttp client for `https://api.hevyapp.com/v1` with auth (`api-key` header), typed errors (auth/conflict/communication), 10s timeouts. Endpoints already implemented: `GET /workouts/count`, `GET /workouts` (paginated), `GET /user/info`, `GET /body_measurements`, `GET /workouts/events?since=...`, `POST /workouts`, `POST /body_measurements`, `PUT /body_measurements/{date}`. **This is the foundation — extract it into the new package nearly verbatim.**
- `custom_components/hevy/coordinator.py` — polling/diffing logic that detects new, updated, and deleted workouts via `/workouts/events`. The event-detection and `since`-cursor seeding logic is worth porting into the sync engine.
- Aggregate computations in `sensor.py` (volume by period, streaks, training time, unique exercises) — port the math into the analytics module.
- `tests/` — 140+ pytest tests with HA stubbed out in `conftest.py`. Port the API-client and data-logic tests; drop the HA-entity tests.
- `requirements.txt`, `.ruff.toml`, CI workflows — keep ruff + pytest + CI working throughout.

**Decision (default — flag if you disagree while working):** the Home Assistant integration under `custom_components/hevy/` is RETIRED. Move reusable code out, then delete `custom_components/`, the HA `config/` dev folder, and HA-specific tests. The repo becomes a single-purpose standalone tool. Update README accordingly.

# Target architecture

```
hevy_brain/
├── __init__.py
├── cli.py              # entry point: `hevy-brain sync|analyze|coach|push|full`
├── config.py           # loads config.toml + env vars (vault path, intervals, units)
├── api/
│   └── client.py       # HevyApiClient (ported from custom_components/hevy/api.py)
├── store/
│   └── cache.py        # local SQLite or JSON cache of ALL workouts ever fetched
│                       # (full-history backfill via pagination; incremental via /workouts/events)
├── vault/
│   ├── writer.py       # safe markdown writer: atomic writes, never touches files outside
│   │                   # VAULT_SUBFOLDER, preserves user edits outside managed blocks
│   ├── workouts.py     # one note per workout
│   ├── exercises.py    # one evergreen note per exercise
│   └── dashboards.py   # weekly/monthly reviews + main dashboard
├── analytics/
│   ├── stats.py        # volume, streaks, PRs, frequency, training time (port from sensor.py)
│   ├── patterns.py     # muscle-group balance, plateau detection, progressive-overload
│   │                   # tracking, deload signals, consistency/time-of-day patterns
│   └── prs.py          # per-exercise PR history (max weight, est. 1RM via Epley, rep PRs)
├── coach/
│   └── advisor.py      # Anthropic API integration (see AI Coach section)
└── writeback/
    └── hevy_push.py    # create workouts / log measurements in Hevy (see Write-back section)
tests/                  # pytest, no HA stubs needed anymore
scripts/
└── register_task.ps1   # Windows Task Scheduler registration for scheduled sync
```

# Obsidian vault output spec

All notes go under `VAULT_PATH/VAULT_SUBFOLDER/`. Use YAML frontmatter on every note so Dataview/Bases queries work. Use `[[wikilinks]]` between workouts ↔ exercises ↔ reviews.

```
Fitness/Hevy/
├── Dashboard.md                      # stats overview, current streak, recent PRs, links
├── Workouts/
│   └── 2026-06-09 Push Day.md        # one per workout: frontmatter (date, title, duration_min,
│                                     # volume_kg, exercise_count, total_reps, hevy_id) +
│                                     # exercise tables (sets × reps × weight) + PR callouts +
│                                     # wikilinks to each exercise note
├── Exercises/
│   └── Bench Press (Barbell).md      # evergreen: PR history, est. 1RM trend, last performed,
│                                     # frequency, all-time volume, link to every workout using it
├── Measurements/
│   └── Body Log.md                   # body weight / fat % / lean mass time series table
├── Reviews/
│   ├── 2026-W23 Weekly Review.md     # auto-generated weekly: volume vs prior week, muscle
│   │                                 # balance, PRs, AI coach insights section
│   └── 2026-06 Monthly Review.md
└── Coach/
    └── 2026-06-09 Recommendations.md # AI coach output (see below)
```

**Idempotency rules (critical):** syncing twice must produce zero diffs. Workout notes are keyed by Hevy workout ID (stored in frontmatter). If a note exists, update only the managed content; if I've added my own notes below a `%% hevy-brain:end %%` marker, preserve them. Deleted workouts in Hevy move their note to an `Archive/` subfolder rather than deleting (my vault is a second brain — never destroy my data).

# Analytics (deterministic, no AI needed)

Compute from the full local cache, not just recent workouts:

1. Volume per muscle group per week (map exercises → muscle groups via Hevy's exercise template data; fall back to a name-based mapping table that I can edit in `config.toml`)
2. PR detection: max weight, max reps at weight, estimated 1RM (Epley), session volume PRs
3. Plateau detection: an exercise whose est. 1RM hasn't improved in N weeks (default 4) while being trained ≥ weekly
4. Imbalance detection: push/pull volume ratio, leg/upper ratio outside configurable bands
5. Consistency: streaks, sessions/week trend, average duration, time-of-day pattern
6. Overload tracking: per-exercise week-over-week volume and intensity deltas

These feed both the markdown dashboards and the AI coach context.

# AI Coach (Anthropic API)

A `coach` module that turns the analytics + recent workout history into actionable advice, written to `Coach/` notes and embedded in weekly reviews.

- Use the official `anthropic` Python SDK. Model: **`claude-opus-4-8`** (exact string, no date suffix). Use `thinking={"type": "adaptive"}` and `output_config={"effort": "high"}`. Do **not** pass `temperature`/`top_p`/`top_k` (removed on this model — they 400).
- Use **structured outputs** (`client.messages.parse()` with a Pydantic model) so coach output is machine-readable: list of findings, each with `category` (plateau | imbalance | recovery | progression | alternative), `evidence`, `recommendation`, and for alternatives a proposed concrete exercise swap.
- Use streaming for any long generation (`client.messages.stream()` + `get_final_message()`).
- Prompt-cache the static system prompt; pass volatile analytics data in the user turn.
- The coach must ground every claim in the supplied data (cite exact numbers/dates) — instruct this in its system prompt.
- **Exercise alternatives:** when recommending a swap, the coach must pick from Hevy's actual exercise catalog (fetch/caches exercise templates from the API if an endpoint exists; otherwise from exercises seen in my history + a curated static list), so any suggested routine can be pushed back to Hevy without manual mapping.
- Budget guard: a config cap on coach invocations per day; coach failures must never break the sync.

# Write-back to Hevy (automation)

Module that pushes changes TO Hevy using the existing POST/PUT client methods:

1. `hevy-brain push workout <file.md>` — parse a planned-workout markdown note (define a simple template) and create it in Hevy via `POST /workouts`.
2. `hevy-brain push measurement --weight 78.4` — log body measurement (handle the 409-on-existing-date by falling back to PUT, as the existing services.py already does).
3. Coach-proposed routines render as a planned-workout note with a one-line command to push it — **write-back always requires my explicit command; never auto-mutate my Hevy account.** Read-only sync is fully automatic; writes are human-triggered.

# Scheduling / automation

- `hevy-brain full` = sync → analytics → vault regeneration (no coach call).
- `hevy-brain coach` = generate coach note (intended weekly).
- `scripts/register_task.ps1` registers: `full` every 60 min, `coach` weekly Sunday evening. Log to a rotating file under the repo; exit non-zero on failure.

# Phases (work through in order, verify each before moving on)

1. **Scaffold + port:** create `hevy_brain` package, port `HevyApiClient` + its tests, add `pyproject.toml` with `hevy-brain` console script. Gate: `pytest` green, `ruff check` clean.
2. **Cache + full backfill:** paginated full-history fetch, incremental sync via `/workouts/events` with persisted cursor. Gate: unit tests with recorded/mocked API fixtures; running sync twice is a no-op.
3. **Vault writer + workout/exercise notes:** Gate: golden-file tests (input fixture workouts → exact expected markdown); idempotency test; path-traversal safety test (writer refuses paths outside VAULT_SUBFOLDER).
4. **Analytics + dashboards/reviews:** port math from `sensor.py` with its tests. Gate: analytics unit tests with known-answer fixtures.
5. **AI coach:** Gate: unit tests with mocked Anthropic client (never call the real API in tests); one real smoke invocation only if `ANTHROPIC_API_KEY` is set, otherwise skip.
6. **Write-back + CLI polish + scheduler script.** Gate: full test suite green; `hevy-brain --help` documents every command.
7. **Cleanup:** remove HA integration, dead deps, HA-specific tests and CI steps; rewrite README for the new tool (install, config, commands, vault layout, automation setup). Gate: CI workflow passes; no references to homeassistant remain in `requirements`/imports.

If `HEVY_API_KEY` is present in the environment, finish with a real end-to-end run against my account (read-only: sync + analytics + vault generation into a temp directory first, print the diff summary, then the real vault) and show me a sample generated workout note in your final report.

# Definition of done

- [ ] `hevy-brain full` syncs my complete Hevy history into the vault structure above, idempotently
- [ ] Incremental runs pick up new/edited/deleted workouts via `/workouts/events`
- [ ] Dashboard, exercise notes, weekly review generate with correct stats (spot-check against Hevy app numbers)
- [ ] `hevy-brain coach` writes a grounded, structured recommendations note
- [ ] `hevy-brain push measurement` and `push workout` work against the real API (demonstrate measurement push only if I confirm)
- [ ] Tests green, ruff clean, CI updated, README rewritten, old HA code removed
- [ ] Final report: what was built, every salvaged-vs-new decision made, sample output note, and how to register the scheduled tasks

# Working style

- Keep a brief running narration only at phase boundaries and when something forces a design change.
- Prefer porting proven code over rewriting; match the existing code style (ruff-formatted, `from __future__ import annotations`, typed).
- All file writes into the vault must be atomic (write temp + rename) and UTF-8 (no BOM).
- Never log or echo the Hevy or Anthropic API keys.
