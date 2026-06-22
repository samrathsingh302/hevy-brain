# hevy-brain — Handoff (single-writer pointer; local folder still `HA-hevy`)

**Current state (22/06/2026):** `main` reconciled, green, and **pushed to origin**. The 16/06 morning-fix is merged over the warm-up-e1rm fix: **P1** warm-up contamination fixed via one shared `models.is_warmup()` helper (handles both `type` and `set_type` keys; excludes warm-ups from `best_e1rm`/`best_set`, keeps them in weight/volume) — this **superset** version replaced the earlier inline `f581b81` fix in the merge (that commit is retained in history); **P1** process-wide cache lock (stops the Sunday-19:00 sync/coach `save()` clobber race — now live); **C1** vault-writer per-note resilience; **C5** CSV formula-injection neutralised. Gate: **458 pytest passed, ruff + mypy clean** (13 warm-up tests green). The `_old/main` warm-up handoff (`docs/handoffs/2026-06-16-warmup-e1rm-fix.md`) is rescued onto main. Vault Hevy path is now `C:\Users\samra\vault\Hevy\`.

**Do next:**
- **Codex debt:** `cd C:/Users/samra/repos/HA-hevy ; codex review --base 05af146` (read-only) when credits are back — covers the warm-up redo + cache-lock + vault-writer + CSV commits.
- **Remaining audit items (not yet fixed):** atomic `vault/writer.py` write; UTC→Europe/London calendar-day (~25 sites); coach `--api` persist-order; empty-routines/measurements guard; corrupt-cache guard; `anthropic>=0.40` floor.
- **Known un-fixed app behaviour:** `max_weight_kg`/`top_weight_kg` still count warm-up sets app-wide (a heavy warm-up can register a top-weight PR) — deliberately deferred (larger blast radius).
- **User-gated (needs you):** live-prove slice-12 adherence capture; pre-public — rotate `HEVY_API_KEY` then `gh repo edit --visibility public`; audit `config.toml` in git history (username + old path, no key — history rewrite is irreversible). Optional: rename the local folder `HA-hevy` → `hevy-brain` to match the GitHub repo.

**Changelog (newest first):**
- **22/06/2026** — fleet reconciliation: morning-fix merged→main (is_warmup superset resolution) + pushed; orphan warm-up handoff rescued; vault rename finished; this handoff collapsed.
- **16/06/2026** — morning-fix: warm-up est-1RM (is_warmup helper) + cache-lock + vault-writer resilience + CSV-injection (458 tests, verifier SHIP).
- **15/06/2026** — overnight autonomous build: 6 analytics slices (progression targets, consistency heatmap, `export --csv`, `diff`, deload-readiness, volume-landmark/MEV) shipped + pushed (338→444, 90% cov).
- **14/06/2026** — overnight audit: A1 (coach budget soft-cap accepted) + A2 (coach save-failure handling) merged; ruff format wave.
- **12–13/06/2026** — slices 1–17: core build (routines sync/edit, knowledge bridge, guide/redesign, write-back trio, charts, coach memory, year-in-review, doctor, Tier-1 hardening).

**Latest dated handoffs:** `docs/handoffs/2026-06-16-morning-fix-warmup-cachelock.md` · `docs/handoffs/2026-06-16-warmup-e1rm-fix.md` · `docs/handoffs/2026-06-15-overnight-autonomous.md`.
