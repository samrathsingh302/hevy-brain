# hevy-brain (HA-hevy) — TASKS (live planning doc)

**Last updated:** 22/06/2026 · **Maintainer:** Samrath (+ Claude sessions)

How this works: **Read this → plan the session → do the work → update `HANDOFF.md` at session end → when every task is done, archive this file to `docs/archive/TASKS-<date>-done.md`.** Living doc — edit freely as work changes. Buckets: 🔴 Do-next · 🟠 Important · 🟡 Backlog · ⚙ Manual (Samrath-only). (Remote is already `hevy-brain.git`; the local folder is still `HA-hevy` — see ⚙ rename.)

---

## 🔴 Do-next
_(none — gates are green (458 pytest + ruff + mypy; the red Lint CI was fixed 22/06). The headline functional task is the UTC→London fix below.)_

## 🟠 Important
- [ ] **UTC→Europe/London calendar-day fix** — a UK-evening workout / "today" currently lands on the wrong civil day for filenames + date windows (everything uses `datetime.now(tz=UTC)`). Fix = a central London-`ZoneInfo` clock helper (none exists yet). **Core actionable = 7 civil-day sites:** `cli.py:189,265,380,459,673` · `vault/build.py:24` · `writeback/hevy_push.py:545`. Broader surface: 13 `.now(tz=UTC)` calls across 6 files; ~49 date/time-coupled lines; 80-line superset incl. ISO-parse (Hevy timestamps treated as UTC). The "~25 sites" in old handoffs = the audit estimate; the 7 above are what a London fix changes. _(source: prior HANDOFF; 2026-06-16-morning-fix-warmup-cachelock.md:54-55)_

## 🟡 Backlog
- [ ] **`anthropic>=0.40` floor** — pin a minimum in `pyproject.toml` (installed locally is 0.109.1). _(source: prior HANDOFF)_
- [ ] **corrupt-cache guard** — a hand-edited/corrupt `coach_calls` etc. → AttributeError; `hevy_brain/coach/advisor.py:224`. _(source: docs/handoffs/2026-06-14-overnight-audit.md:60)_
- [ ] **empty-routines / empty-measurements guard** — degrade cleanly on an account with none. (Spec lives vault-side in the nightly-audit `03-FIXES.md` §2/§3.) _(source: prior HANDOFF)_
- [ ] **Known-deferred app behaviour** — `max_weight_kg`/`top_weight_kg` still count warm-up sets app-wide (a heavy warm-up can register a top-weight PR). Deliberately deferred (blast radius). _(source: prior HANDOFF; -warmup-cachelock.md:21-22)_

## ⚙ Manual (Samrath-only)
- [ ] **Codex re-run debt** — `cd C:/Users/samra/repos/HA-hevy ; codex review --base 05af146` (read-only) — covers the warm-up redo + cache-lock + vault-writer + CSV commits **and** the 22/06 ruff-format commit. Blocker: ChatGPT-sub credits. _(source: prior HANDOFF)_
- [ ] **Folder rename `HA-hevy` → `hevy-brain`** (machine-level) — the GitHub repo is already `hevy-brain`; the local dir + external path refs remain. ⚠ The live **hourly sync + Sunday-19:00 coach Task Scheduler jobs hardcode `…\HA-hevy\`** + the mission-deck launcher — those must be re-pointed. In-repo refs to fix: `HANDOFF.md`, `docs/_archive/VERIFY-AND-CLOSEOUT-2026-06-14.md`. Do NOT touch the upstream-fork links `hudsonbrendon/HA-hevy` (CHANGELOG.md:192, README.md:209 — a different repo). _(source: prior HANDOFF)_
- [ ] **Pre-public (user-gated)** — rotate `HEVY_API_KEY` then `gh repo edit --visibility public`; rewrite `config.toml` out of git history (4 commits hold username + old path, **no key** — irreversible); gitignore `.mcp.json`; live-prove slice-12 adherence. _(source: prior HANDOFF; 2026-06-14-overnight-audit.md:61)_
- [ ] **Delete the `_old/*` anchor branches** — verified fully absorbed (0-orphan vs `main`). Kept as insurance — **safe to run:** `git -C C:/Users/samra/repos/HA-hevy branch -D _old/main _old/overnight-audit-2026-06-14`. _(source: fleet-finalisation 22/06 verify)_

---
**✅ Already DONE (do not re-open — old handoffs listed these as "remaining"; the 22/06 harvest proved them shipped):**
- **Atomic vault write** — `hevy_brain/vault/writer.py:89-118` already does `mkstemp`(same dir)+`replace()` with a 5× Windows-lock retry (since `50205bd`).
- **Coach `--api` persist-order** — `record_call`+`store.save()` already precede `_save_focus` (`cli.py:343-349`); only the inherent soft-cap nuance remains, and that was explicitly accepted (single-user CLI).
- **CSV formula-injection** — `_csv_safe` shipped (`5491ab4`).

_Codex two-pass note: the 22/06 run's only code change was the ruff-format reformat (semantically inert; verified by all 4 gates green). The `--base 05af146` Codex pass above now also covers it. Gate to re-run on code work: `python -m pytest tests -q` + `ruff check .` + `ruff format . --check` + `mypy hevy_brain`._
