# hevy-brain — Claude Code instructions
**Read order, every session:** 1) this file · 2) HANDOFF.md (always — current state, gotchas)
· 3) C:\Users\samra\projects\_shared-context\SAMRATH.md + PROMPTING_GUIDE.md + ORCHESTRATION.md (who you work for, how we prompt, how to split work across agents)
· 4) PROMPT.md (the original build spec named in HANDOFF). If _shared-context is unreachable, say so; key defaults:
free tiers only · British English, dd/mm/yyyy, £ · evidence over intuition · tests with code ·
no data loss · don't ask about things SAMRATH.md §3 lets you decide; always ask about §4.

## What this is
A standalone Python CLI that syncs your full Hevy workout history into an Obsidian second brain
(`Hevy/` subfolder), analyses training patterns, gives free AI coaching, and pushes changes back to
Hevy. For Samrath, personal use. Done = sync/vault/coach/push all run cleanly against the real account.

## Stack & layout
- Python ≥3.12, packaged via `pyproject.toml` (setuptools); deps: aiohttp, PyYAML, pydantic, anthropic.
- `hevy_brain/`: `cli.py` (dispatch) · `config.py` · `api/client.py` (Hevy client) · `sync.py` (full +
  incremental `/workouts/events`) · `store/cache.py` (local JSON, source of truth) · `models.py` ·
  `analytics/` (stats, prs, patterns) · `vault/` (writer + builders) · `coach/advisor.py` · `writeback/`.
- Config: `config.toml` (vault path + subfolder). Data cache in `data/` — gitignored, never committed.
- Test: `python -m pytest tests -q` (offline, no network). Lint: `python -m ruff check hevy_brain tests`.

## Fences
Never: write outside the `Hevy/` vault subfolder (path-traversal guard) · do non-atomic vault writes ·
overwrite user edits below the `%% hevy-brain:end %%` marker (preserve them on regen) · delete a
workout note (archive to `Archive/`, never destroy) · put the Hevy key anywhere but the `HEVY_API_KEY`
env var (never config or git) · hit the real Hevy account in tests (offline only — fixtures/mocks) ·
auto-write to Hevy (writes only via explicit `push` commands). Data/cache/notes stay gitignored.

## Working style
One slice per session · decompose across agents first (ORCHESTRATION.md: how does this split?) ·
commit per coherent step, push per session · tests written with code ·
end every session: update HANDOFF + CHANGELOG, emit the carry-on prompt (PROMPTING_GUIDE §4).
