# hevy-brain — Claude Code instructions
**Read order, every session:** 1) this file · 2) current state = newest dated handoff in `C:\Users\samra\OneDrive\dev\repos\hevy-brain\handoffs\` (always — gotchas; handoffs moved to the vault 26/06/2026, no repo HANDOFF.md)
· 3) identity + build spec live in this CLAUDE.md (there is no `prompts\PROMPT.md`). House doctrine, defaults and the session ritual load from the global `~/.claude/CLAUDE.md` — not restated here (trimmed 05/08/2026).

## What this is
A standalone Python CLI that syncs your full Hevy workout history into your Obsidian second brain,
analyses training patterns, gives free AI coaching, and pushes changes back to Hevy. The generated
notes live at `C:\Users\samra\OneDrive\brain\hevy\` (a top-level vault zone — see Config; 01/07/2026, moved
in from the old repo `vault_staging/`). For Samrath, personal use. Done = sync/vault/coach/push all run
cleanly against the real account.

## Stack & layout
- Python ≥3.12, packaged via `pyproject.toml` (setuptools); deps: aiohttp, PyYAML, pydantic, anthropic.
- `hevy_brain/`: `cli.py` (dispatch) · `config.py` · `api/client.py` (Hevy client) · `sync.py` (full +
  incremental `/workouts/events`) · `store/cache.py` (local JSON, source of truth) · `models.py` ·
  `analytics/` (stats, prs, patterns) · `vault/` (writer + builders) · `coach/advisor.py` · `writeback/`.
- Config: `config.toml` (the `[vault]` `path` + `subfolder` keys → output at `C:\Users\samra\OneDrive\brain\hevy\`; gitignored, local-only). Data cache in `data/` — gitignored, never committed.
- Test: `python -m pytest tests -q` (offline, no network). Lint: `python -m ruff check hevy_brain tests`.

## Fences
Never: write outside the configured output subfolder (`hevy`, under `C:\Users\samra\OneDrive\brain\`;
path-traversal guard) · do non-atomic writes there · overwrite user edits below the `%% hevy-brain:end %%` marker (preserve them on regen) · delete a
workout note (archive to `Archive/`, never destroy) · put the Hevy key anywhere but the `HEVY_API_KEY`
env var (never config or git) · hit the real Hevy account in tests (offline only — fixtures/mocks) ·
auto-write to Hevy (writes only via explicit `push` commands). Data/cache/notes stay gitignored.

## Working style
One slice per session · commit per coherent step, push per session · tests written with code.

---

## Two vault destinations — don't conflate them
The app's **product output** (generated Hevy notes) writes to the top-level hevy zone at `C:\Users\samra\OneDrive\brain\hevy\`; all **working/session md** lives at `C:\Users\samra\OneDrive\dev\repos\hevy-brain\` (`handoffs\` newest dated file = current state · `tasks.md` · `logs\` `specs\` `plans\` `guides\` `prompts\`). Neither belongs in this repo — it keeps only code + `README.md` + `CLAUDE.md` + skills/agents + fixtures + product content. Session ritual (catch-up, handoff at close, split-when-large, seeded spawns) = the global contract in `~/.claude/CLAUDE.md` (trimmed 05/08/2026; ROUTER retired).
