# hevy-brain — Claude Code instructions
**Read order, every session:** 1) this file · 2) current state = newest dated handoff in `C:\Users\samra\vault\dev\handoffs\HA-hevy\` (always — gotchas; handoffs moved to the vault 26/06/2026, no repo HANDOFF.md)
· 3) C:\Users\samra\vault\_shared-context\SAMRATH.md + LOOP-GUIDE.md (who you work for; how we prompt + split work across agents + run the autonomous loop — LOOP-GUIDE consolidates the former PROMPTING_GUIDE + ORCHESTRATION)
· 4) `C:\Users\samra\vault\dev\prompts\HA-hevy\PROMPT.md` (the original build spec). If _shared-context is unreachable, say so; key defaults:
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
One slice per session · decompose across agents first (LOOP-GUIDE.md §3: how does this split?) ·
commit per coherent step, push per session · tests written with code ·
end every session: write a dated handoff to `C:\Users\samra\vault\dev\handoffs\HA-hevy\` (newest = current state), emit the carry-on prompt (LOOP-GUIDE.md §14).

---

## Markdown lives in the vault `dev/` zone (26/06/2026 — supersedes "repo reality wins" for working md)
All working/generated markdown for **HA-hevy** now lives in the Obsidian vault, NOT in this repo:
- **Handoffs** -> `C:\Users\samra\vault\dev\handoffs\HA-hevy\` — newest dated file = current state (no `HANDOFF.md` in the repo anymore)
- **Tasks** -> `C:\Users\samra\vault\dev\tasks\HA-hevy.md`
- **Logs** `dev\logs\HA-hevy\` · **Specs** `dev\specs\HA-hevy\` · **Plans** `dev\plans\HA-hevy\` · **Guides** `dev\guides\HA-hevy\` · **Prompts** `dev\prompts\HA-hevy\`
End a session by writing a dated handoff `YYYY-MM-DD-HHmm-<slug>.md` to `dev\handoffs\HA-hevy\`. Write all of the above there, never in this repo. This repo keeps only code + `README.md` + `CLAUDE.md` + skills/agents + fixtures + product content; a few design docs that code loads by path stay here by necessity. Cheap context: vault `dev\index.md` + `ROUTER.md` route intent -> exact file.
