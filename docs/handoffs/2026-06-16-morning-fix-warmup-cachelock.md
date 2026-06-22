# 2026-06-16 — Morning fix run: HA-hevy 2× P1 (warm-up maths + cache lock)

Executed from the 16/06 nightly-audit queue
(`vault/raw/coding/nightly-audit-2026-06-16/03-FIXES.md`). Both HA-hevy P1s —
the only live P1s in the whole audit — are fixed, verified and committed on
`fix/morning-2026-06-16` (off `main` @ `05af146`). **NOT pushed — Samrath's gate.**

## P1(a) — warm-up contamination of est-1RM · commit `1ff0cc2`
`prs._session_entry` counted warm-up sets when computing `best_e1rm_kg`/`best_set`,
so a heavy low-rep warm-up out-Epley'd the working set — corrupting plateau
detection, the per-lift "aim for X" progression target, e1RM charts/PRs and coach
memory. It would have biased the post-lapse `guide return` flow. (HA-hevy's own
HANDOFF parked this as a known "fix supervised" item.)

Fix: one `is_warmup()` helper (`models.py`) treating **either** `type` (cache sets)
**or** `set_type` (exercise_history sets) as a warm-up. `prs._session_entry` AND
`reconcile.aggregate_server` exclude warm-ups from est-1RM **only**, in the SAME
commit — weight/volume/session-count stay warm-up-INCLUSIVE on both sides, so
`verify exercise` (F4) still reconciles (no false drift). The 5 existing inline
warm-up filters (deload/redesign/sessiondiff/session_quality/heatmap) were unified
onto the helper. `max_weight_kg`/`volume_kg` stay warm-up-inclusive app-wide (the
audit's stated call — flag if you want a heavy warm-up to stop registering a
top-weight PR too). +6 regression tests.

## P1(b) — cache has no inter-process lock · commit `f12c4c7`
Every command builds its own CacheStore; `save()` rewrites all 8 JSON files from an
in-memory snapshot with no lock spanning the read-modify-write. The shipped schedule
overlaps the hourly sync (:05) with the Sunday coach (19:00) weekly → last-writer-wins
silently drops the just-synced workouts/cursor.

Fix: `cache_lock(data_dir)` — an OS advisory lock (`msvcrt` on Windows / `fcntl` on
CI Linux), non-blocking, auto-released by the OS on crash. `main()` wraps the four
writer commands (sync/full/coach/push); a busy second run skips cleanly (exit 0,
"another run in progress"). Also closes the third unlocked save
(`_track_draft_adherence`). +6 tests (incl. a `main()` skip-wiring integration test).

## Verification
- **456 offline tests pass** (was 444); ruff + mypy clean (47 source files).
- P1(a): **3** fresh-Opus refute-skeptics → unanimous SHIP. Runtime smoke on the real
  285-workout cache: `doctor`/`status` + `diff` (overall) + `diff` per-exercise
  (`Triceps Extension (Cable)` est-1RM 27.2→30.0 — correct Epley on real data).
- P1(b): **2** fresh-Opus refute-skeptics → unanimous SHIP (writer set complete vs
  every `store.save()`; no fd leak; `.lock` gitignored; fcntl/msvcrt exclusion sound).
  Skip-path smoke: a `coach` fired while the lock is held returns 0 without side effects.
- **Codex verification DEBT** (Codex out this session, per Samrath's standing call):
  re-run `codex review --commit 1ff0cc2` and `codex review --commit f12c4c7` once credits
  are topped up.

## Not done / gates
- **PUSH** `fix/morning-2026-06-16` — Samrath's gate (local-only).
- Pre-existing uncommitted doc edits (`CLAUDE.md`, `HANDOFF.md`,
  `docs/VERIFY-AND-CLOSEOUT-2026-06-14.md`) were left untouched — they predate this run.
- Remaining HA-hevy audit items NOT done (carried to §2/§3 of the morning queue):
  atomic `vault/writer.py:92` (C1), CSV-injection `export.py:98` (P3), UTC→Europe/London
  calendar-day ~25 sites (P2, angle-B), coach `--api` persist-order `cli.py:350/360` (P2),
  empty-routines/measurements guard (P2/P3), corrupt-cache guard (P2), `anthropic>=0.40`
  floor (P2). All in `03-FIXES.md`.
