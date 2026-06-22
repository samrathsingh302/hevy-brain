# hevy-brain — HANDOFF (thin single-writer pointer; local folder still `HA-hevy`)

**Current state (22/06/2026):** `main`, **pushed and in sync with `origin/main`** (remote = `hevy-brain.git`), tree clean. **Gates GREEN: 458 pytest · ruff check · ruff format · mypy** (all re-run 22/06). ⚠ **The Lint CI was RED on HEAD `6798dac`** (`ruff format --check` failed on 9 drifted files) despite the prior handoff saying "green" — **fixed this run** (semantically-inert reformat; all gates re-verified green). Core build complete; the 16/06 morning-fix (warm-up e1RM via `is_warmup()`, process-wide cache lock, vault-writer resilience, CSV-injection) is merged. **Health: green (CI now green after the format fix); one functional task open (UTC→London), the rest backlog/manual.**

**Next → see [`TASKS.md`](TASKS.md).** (🟠 the UTC→Europe/London calendar-day fix — 7 core sites — is the head of the queue.)

**✅ Corrected drift:** old handoffs listed "atomic vault write" + "coach `--api` persist-order" as *remaining* — both are **already shipped** (`writer.py:89-118`; `cli.py:343-349`). See `TASKS.md`.

**Changelog (newest first):**
- **22/06/2026** — fleet finalisation: **fixed red Lint CI** (`ruff format` on 9 drifted files; all 4 gates re-verified green); installed `TASKS.md`; collapsed this HANDOFF (corrected the atomic-write/persist-order drift); archived spent `OVERNIGHT-PLAN`/`VERIFY-AND-CLOSEOUT`; pruned merged `fix/morning-2026-06-16` + `overnight-audit-2026-06-14`; `_old/*` deletion routed to TASKS ⚙.
- **22/06/2026** — fleet reconciliation: morning-fix merged→main (is_warmup superset) + pushed; orphan warm-up handoff rescued; vault rename finished.
- **16/06/2026** — morning-fix: warm-up est-1RM + cache-lock + vault-writer resilience + CSV-injection (458 tests, verifier SHIP).
- **15/06/2026** — overnight autonomous build: 6 analytics slices shipped + pushed (338→444, 90% cov).
- **14/06/2026** — overnight audit: A1 (coach budget soft-cap) + A2 (coach save-failure handling) merged; ruff format wave.

**Latest dated handoffs:** `docs/handoffs/2026-06-22-2008-fleet-finalisation.md` · `docs/handoffs/2026-06-16-morning-fix-warmup-cachelock.md` · `docs/handoffs/2026-06-15-overnight-autonomous.md`.
