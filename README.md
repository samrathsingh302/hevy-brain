# Hevy Second Brain (`hevy-brain`)

[![Lint](https://github.com/samrathsingh302/HA-hevy/actions/workflows/lint.yml/badge.svg)](https://github.com/samrathsingh302/HA-hevy/actions/workflows/lint.yml)
[![Test](https://github.com/samrathsingh302/HA-hevy/actions/workflows/test.yml/badge.svg)](https://github.com/samrathsingh302/HA-hevy/actions/workflows/test.yml)

Sync your complete [Hevy](https://www.hevy.com/) workout history into an
**Obsidian second brain**, analyze your training patterns, get AI coaching
grounded in your real numbers, and push changes back to Hevy — so you rarely
have to edit the Hevy app by hand.

> Originally forked from the excellent
> [hudsonbrendon/HA-hevy](https://github.com/hudsonbrendon/HA-hevy) Home
> Assistant integration. The battle-tested Hevy API client and sync logic
> were ported from it; the Home Assistant integration itself has been retired
> from this repo.

## What it does

- **Full sync** — backfills your entire workout history once, then pulls only
  changes via Hevy's `/workouts/events` endpoint (new, edited, and deleted
  workouts) on every run. Body measurements are replaced wholesale on each
  sync and deduplicated by date — if Hevy returns more than one entry for the
  same date, the last one silently wins.
- **Obsidian notes** — one note per workout (set-by-set tables, PR callouts),
  one evergreen note per exercise (PR history, est. 1RM), a dashboard, body
  measurement log, and weekly/monthly reviews. All with frontmatter for
  Dataview/Bases and wikilinks between everything.
- **Analytics** — volume per muscle group, push/pull balance, streaks,
  plateau detection (stalled est. 1RM), and week-over-week overload tracking.
- **AI coach (free by default)** — `hevy-brain coach` writes a self-contained
  *briefing* note (your computed stats + the coaching instructions). Open it
  in Claude Code or claude.ai under your existing subscription — **no API key,
  no per-call cost.** An opt-in `--api` flag uses the metered Anthropic API
  for full automation instead. Either way, every claim cites your actual
  numbers and exercise swaps are restricted to exercises that exist in Hevy.
- **Write-back** — log body measurements and create workouts in Hevy from the
  CLI / planned-workout notes. Writes are **always manual**; only reads are
  automated.
- **Safe by design** — never writes outside its vault folder, atomic writes,
  your edits below the `%% hevy-brain:end %%` marker in any note survive
  regeneration, and deleted workouts are archived, never destroyed.

## Install

```powershell
git clone https://github.com/samrathsingh302/HA-hevy
cd HA-hevy
pip install -e .
```

Set your API keys (user-level env vars so scheduled tasks see them):

```powershell
[Environment]::SetEnvironmentVariable('HEVY_API_KEY', '<key from hevy.com/settings?developer>', 'User')
[Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', '<key>', 'User')   # only for `coach`
```

## Configure

Edit [config.toml](config.toml). The config in this repo points at my live
vault (the folder containing `.obsidian`) — repoint it (e.g. at a staging
dir) before reusing:

```toml
[vault]
path = 'C:\Users\samra\Atlas'
subfolder = "Hevy"   # a separate folder; hevy-brain never touches anything else
```

## Use

```text
hevy-brain sync     # fetch new/changed Hevy data into the local cache
hevy-brain vault    # regenerate all Obsidian notes from the cache
hevy-brain full     # sync + vault
hevy-brain coach    # FREE briefing note - analyze it with your Claude sub
hevy-brain coach --api   # opt-in: metered Anthropic API (needs ANTHROPIC_API_KEY)
hevy-brain status   # cache overview
hevy-brain push measurement --weight-kg 78.4 [--fat-percent 17] [--date 2026-06-10]
hevy-brain push workout path\to\plan.md
```

### Vault layout

```
Hevy/
├── Dashboard.md                     # totals, streaks, muscle balance, recent PRs
├── Workouts/2026-06-08 Push Day.md  # per-workout: tables, PR callouts, links
├── Exercises/Bench Press (Barbell).md  # per-exercise: PR history, est. 1RM
├── Measurements/Body Log.md
├── Reviews/2026-W24 Weekly Review.md   # + monthly reviews
├── Coach/2026-06-10 Recommendations.md
└── Archive/                         # notes for workouts deleted in Hevy
```

Anything you write **below** the `%% hevy-brain:end %%` marker in any note is
preserved forever — treat the area above it as generated.

### Planned-workout notes (push to Hevy)

```markdown
---
type: hevy-planned-workout
title: Coach Push Day
start_time: 2026-06-12T17:00:00+00:00
end_time: 2026-06-12T18:00:00+00:00
exercises:
  - name: Bench Press (Barbell)
    exercise_template_id: 79D0BB3A
    sets:
      - { weight_kg: 60, reps: 8 }
      - { weight_kg: 60, reps: 8 }
---
```

Then: `hevy-brain push workout plan.md`. Template IDs are in each exercise
note's frontmatter (synced from Hevy).

## Automate (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

Registers two Task Scheduler jobs: `hevy-brain full` hourly and
`hevy-brain coach` Sundays at 19:00, logging to `logs/`.

## Development

```powershell
pip install -e ".[dev]"
python -m pytest tests -q     # 60 tests, no network, no real API calls
python -m ruff check hevy_brain tests
python -m ruff format hevy_brain tests
```

Architecture: `api/` (Hevy client) → `sync.py` → `store/` (local JSON cache,
source of truth) → `analytics/` + `vault/` (note generation) and `coach/`
(Anthropic). Write-back lives in `writeback/` and is only reachable from
explicit CLI commands.

## License

MIT — see [LICENSE](LICENSE).
