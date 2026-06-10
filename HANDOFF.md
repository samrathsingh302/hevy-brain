# hevy-brain — Handoff

Paste this into a new chat (or just open it in Claude Code from the repo) to
pick up where we left off.

## What this project is

`hevy-brain` is a standalone Python CLI that syncs your [Hevy](https://hevy.com)
workout data into your Obsidian second brain, analyzes training patterns,
gives free AI coaching, and can push changes back to Hevy.

It started as a Home Assistant integration (forked from
hudsonbrendon/HA-hevy) and was fully refactored into this CLI. The HA code is
gone; the proven Hevy API client + sync logic were ported into the new
package.

- **Repo:** https://github.com/samrathsingh302/HA-hevy (private, my account)
- **Local path:** `C:\Users\samra\projects\HA-hevy`
- **Obsidian vault target:** `C:\Users\samra\projects\second-brain\vault`
  (the folder that holds `.obsidian`). hevy-brain only ever writes into the
  `Hevy/` subfolder there — my `inbox`/`notes`/`sources`/`topics` are untouched.

## Current state (as of 2026-06-10)

✅ Done:
- Full package built: `hevy_brain/` (api, sync, store, analytics, vault, coach,
  writeback) + `cli.py`.
- 56 tests pass (`pytest`), ruff lint + format clean. CI updated (test + lint
  workflows; HA-specific `validate.yml`/hassfest/HACS removed).
- Real end-to-end sync ran against my Hevy account: **285 workouts, 29 body
  measurements, 486 exercise templates** cached locally.
- Vault generated into `second-brain\vault\Hevy\` (dashboard, 285 workout
  notes, 124 exercise notes, weekly+monthly reviews, body log).
- Coach is **free by default** — writes a briefing note to analyze via my
  Claude subscription; metered API is opt-in behind `--api`.

⬜ Not done yet (pick up here):
1. **Revoke the old Hevy API key** at https://hevy.com/settings?developer (it
   was pasted into a chat once), generate a fresh one, and set it as a user
   env var so scheduled runs work:
   ```powershell
   [Environment]::SetEnvironmentVariable('HEVY_API_KEY', '<new key>', 'User')
   ```
2. **Register the scheduled tasks** (hourly sync + weekly coach):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
   ```
3. Optional: open `Hevy/Coach/<date> Briefing.md` in Claude and ask it to
   "act as the coach and analyze my data," writing recommendations below the
   `%% hevy-brain:end %%` marker.

## Commands

```text
hevy-brain full     # sync from Hevy + regenerate all notes (the main one)
hevy-brain sync     # fetch new/changed Hevy data into the local cache only
hevy-brain vault    # regenerate notes from the cache (no network)
hevy-brain coach    # FREE briefing note (analyze with Claude subscription)
hevy-brain coach --api   # opt-in metered Anthropic API instead
hevy-brain status   # cache + config overview
hevy-brain push measurement --weight-kg 78.4 [--date 2026-06-10]
hevy-brain push workout path\to\plan.md   # create a workout in Hevy
```

Reads are automatic; **writes to Hevy only happen on explicit `push` commands.**

## Key facts / design

- **Config:** `config.toml` (`[vault] path` + `subfolder = "Hevy"`). Secrets
  never live in config — only env vars `HEVY_API_KEY` and (for `--api`)
  `ANTHROPIC_API_KEY`.
- **Local cache:** `data/` (JSON, gitignored) is the source of truth. Vault can
  be rebuilt offline from it. First sync = full backfill; later syncs are
  incremental via Hevy's `/workouts/events` cursor.
- **Safety:** vault writer is path-jailed to the `Hevy/` folder, writes are
  atomic, anything below the `%% hevy-brain:end %%` marker in a note is
  preserved on regen, deleted workouts get archived (never destroyed).
- **Privacy:** workout data, cache, and generated notes are gitignored — only
  the *code* is on GitHub, never my data or keys.
- **Coach model (for `--api`):** `claude-opus-4-8`, adaptive thinking,
  structured outputs (Pydantic), daily budget cap.

## Architecture map

```
hevy_brain/
├── cli.py              # command dispatch
├── config.py           # config.toml + env vars
├── api/client.py       # HevyApiClient (ported from HA integration)
├── sync.py             # full backfill + incremental /workouts/events sync
├── store/cache.py      # local JSON cache (source of truth)
├── models.py           # raw API payload -> processed workout records
├── analytics/          # stats.py, prs.py, patterns.py
├── vault/              # writer.py (safe), workouts/exercises/dashboards, build.py
├── coach/advisor.py    # briefing (free) + API report (--api)
└── writeback/hevy_push.py  # create workouts / log measurements
scripts/register_task.ps1   # Windows Task Scheduler registration
PROMPT.md                   # original build spec
```

## How to verify it still works

```powershell
cd C:\Users\samra\projects\HA-hevy
pip install -e ".[dev]"
python -m pytest tests -q          # expect 56 passed
python -m ruff check hevy_brain tests
hevy-brain status                  # shows cached counts
```
