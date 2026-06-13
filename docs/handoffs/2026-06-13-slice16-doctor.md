---
status: done
agent: slice16-builder-1
goal: "Slice 16: D2 `hevy-brain doctor` — a read-only health-check command"
outcome: "New hevy_brain/doctor.py + `doctor` command: pure offline checks (Hevy key, Anthropic key, vault path, cache non-empty, sync freshness, vault built) reporting OK/WARN/FAIL; exit 1 only on FAIL. 332 offline tests (was 322), ruff clean. Live: real environment all-green bar the optional Anthropic key — confirmed the hourly sync task is healthy (last synced 0.4h ago)."
gotchas: "run_checks(config, store, now) is PURE — it reads env/config/cache/filesystem only and never calls Hevy, so it's fully unit-testable and safe to run anytime. `now` must be tz-aware UTC; last_sync is a tz-aware ISO string but a hand-edited naive timestamp is tolerated (assumed UTC) so the check never crashes. Scheduled-task health is deliberately NOT checked here (would need a live, untestable schtasks/Get-ScheduledTaskInfo call) — sync freshness is the proxy (>25h stale => the hourly task is probably down). Exit code: 1 only on FAIL; WARN returns 0 (still usable). Output is ASCII (no em-dashes) on purpose so a cp1252 Windows console renders it cleanly — doctor is terminal-only, unlike the markdown notes that rely on _configure_output. Watch: a near-miss this session — inserting _cmd_doctor just before `async def _cmd_verify_exercise` split the `async` from its `def` (the old_string matched the non-async tail); caught by a collection SyntaxError, fixed. When inserting before an `async def`, include `async` in the anchor."
carry-on: "Standalone build queue is drained (roadmap A/C/D complete). Remaining work is user-gated: prove slice 12 adherence capture live (push+train+coach); pre-public checklist (rotate key, flip visibility). Else polish/hardening. E4 stays atlas-pipeline."
---

# 13/06/2026 — Slice 16: D2 `hevy-brain doctor`

Operational polish: one command that tells you whether the unattended pipeline
is healthy, instead of reverse-engineering it from logs and `status`.

## Done (commit b124856, pushed)

1. **`hevy_brain/doctor.py`** (new, pure/offline):
   - `Check` dataclass (`name`, `status`, `detail`); `OK`/`WARN`/`FAIL`.
   - `run_checks(config, store, now)` → Hevy key (FAIL if missing), Anthropic
     key (WARN if absent), vault path exists (FAIL), cache non-empty (FAIL),
     sync freshness (`_sync_freshness`: OK ≤25h, WARN if stale/never/naive-ok),
     vault built (WARN if no `Dashboard.md`).
   - `worst_status(checks)` → fail > warn > ok.
2. **`cli.py`** — `_cmd_doctor` prints `[OK|WARN|FAIL] name: detail`, exits 1
   only on FAIL; `doctor` subparser + dispatch.
3. **Tests** — `tests/test_doctor.py` (10): all-healthy, missing Hevy key
   (fail), missing Anthropic (warn-only), empty cache (fail), stale/never sync
   (warn), naive timestamp tolerated, missing vault path (fail), unbuilt vault
   (warn), `worst_status` precedence.

## Process

No design panel (small, clear). Scope decision: **no scheduled-task probe** —
it would need a live `schtasks`/`Get-ScheduledTaskInfo` call that can't be unit-
tested offline; sync freshness is the testable proxy. ASCII output chosen for a
terminal-only command. **Near-miss caught:** the `_cmd_doctor` insert landed
between `async` and `def _cmd_verify_exercise` (the edit anchor matched the
non-async tail of an `async def`), making `_cmd_verify_exercise` a plain `def`
with an `await` inside — a collection-time SyntaxError flagged it; fixed by
restoring `async` on verify and dropping the stray one from doctor.

## Verify

`python -m pytest tests -q` → **332 passed** (was 322) · `python -m ruff check
hevy_brain tests` → clean. **Live:** `hevy-brain doctor` against the real
environment — Hevy key set, Anthropic key absent (WARN), vault path OK, **285
workouts cached, last synced 0.4h ago** (the hourly task is healthy), vault
built. Overall WARN (the optional key), exit 0.

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Pure `run_checks`, no network** — a diagnostic must be safe to run anytime
  and fully testable.
- **Anthropic absent = WARN, not FAIL** — the free coach path is the default;
  the key is only for `coach --api`.
- **Sync stale threshold 25h** — one hour of slack over the hourly task.
- **Exit 1 only on FAIL** — WARN-level findings are still a usable pipeline.
- **ASCII output** — clean on a cp1252 console (doctor is terminal-only).

## Watch / gotchas

- Editing before an `async def`: include `async` in the anchor, or you split it.
- No task-scheduler probe — sync freshness is the health proxy.
- `HevyBrain Coach` still pending first fire (next Sun 14/06 19:00 — tomorrow).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice16-doctor.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — `logs\coach.log`
> / `Get-ScheduledTaskInfo`)? **The standalone build queue is drained** —
> roadmap sections A, C and D are complete. Remaining work is user-gated, so
> confirm direction before building: (a) **prove slice 12's adherence capture
> live** — push a guide draft (`push routine`), train it, then `coach`;
> (b) **pre-public checklist** — rotate `HEVY_API_KEY`, update the User-scope
> env var, then `gh repo edit --visibility public` (Samrath's explicit call);
> (c) polish/hardening (e.g. a `doctor` scheduled-task probe, more coach depth).
> Offline tests with fixtures, ruff clean, one slice, commit per coherent step,
> push at end, update HANDOFF + dated handoff + carry-on. Locked: explicit-push
> fence; vault rebuildable **offline** (only `verify` makes a read-only network
> call); free tiers; read-only knowledge bridge (never write pipeline folders,
> never read sources/); bodyweight/body data stays off anything published; repo
> private until key rotation. E4 stays an atlas-pipeline task. Do not
> re-litigate.
