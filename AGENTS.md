# AGENTS.md — hevy-brain

> Onboarding for ANY coding agent. Claude Code also reads `CLAUDE.md` (which wins on conflict). Locked decisions live vault-side in `vault\dev\repos\hevy-brain\DECISIONS.md` — read before proposing changes.

## What this is
A standalone Python CLI that syncs full Hevy workout history into an Obsidian vault, analyses training patterns, gives free AI coaching, and pushes changes back to Hevy on explicit command. Single-user (Samrath), personal use. Generated notes land in `C:\Users\samra\vault\life\Hevy\`; the local JSON cache is the source of truth and the vault is rebuildable offline from it.

## Architecture (10 lines)
- Python ≥3.12, setuptools packaging (`pyproject.toml`); deps: aiohttp, PyYAML, pydantic, anthropic, tzdata.
- `hevy_brain/cli.py` — dispatch for ~19 subcommands (sync, vault, full, coach, ask, status, diff, export, doctor, push…).
- `api/client.py` — async Hevy API client.
- `sync.py` — full backfill + incremental via the `/workouts/events` cursor.
- `store/cache.py` — local JSON cache = source of truth.
- `models.py` — record building; times converted to Europe/London once at build.
- `analytics/` — stats, PRs, patterns, progression, deload, landmarks, sessiondiff, comeback, strength-ratio.
- `vault/` — path-jailed atomic writer (`writer.py`) + note builders + heatmap.
- `coach/` — free briefing by default; metered `--api` path is explicit opt-in.
- `writeback/` — reachable ONLY from explicit `push` commands; `clock.py` = London civil-day clock.

## Build / test / run
```
pip install -e ".[dev]"                          # dev install (run from the repo root — see caveat)
python -m pytest tests -q                        # 482 tests
python -m ruff check hevy_brain tests            # lint (ruff pinned 0.15.20)
python -m ruff format hevy_brain tests           # format
mypy hevy_brain                                  # types (mypy pinned 2.1.0)
py -3.12 -m hevy_brain.cli <command>             # RUN THE CLI THIS WAY (see caveat)
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1   # scheduled jobs (full hourly, coach Sun 19:00)
```
**Caveat (open issue #13):** the editable install may point at the deleted `HA-hevy` path and the `hevy-brain` console script resolves to a dependency-less Python 3.14 shim. Use `py -3.12 -m hevy_brain.cli`, never `hevy-brain.exe`; fix = `py -3.12 -m pip install -e .` from the repo root.

## Fences (hard rules)
- Never write outside the configured vault subfolder `life/Hevy` (path-traversal guard exists — keep it).
- Vault writes are atomic (mkstemp+replace) and never overwrite user edits below the `%% hevy-brain:end %%` marker.
- Never delete a workout note — archive to `Archive/`.
- `HEVY_API_KEY` / `ANTHROPIC_API_KEY` live in env vars only — never config, never git. The repo is PUBLIC.
- Tests never touch the real Hevy account — offline fixtures/mocks only.
- No automated writes to Hevy — writeback only via explicit `push` commands.
- Data/cache/notes/config stay gitignored; working markdown (handoffs/plans/tasks) lives in `vault\dev\repos\hevy-brain\`, never in the repo.

## Definition of done
Green gate = pytest + ruff check + ruff format --check + mypy, AND `sync/vault/coach/push` run cleanly against the real account. Every session ends with a dated 6-key handoff in `vault\dev\repos\hevy-brain\handoffs\` + tasks.md updated + a commit — a session without its handoff has failed its exit.

## Where state lives
Current state = the newest dated file in `C:\Users\samra\vault\dev\repos\hevy-brain\handoffs\` + `vault\dev\repos\hevy-brain\tasks.md` (open issues under `## Issues` / GitHub issues).
