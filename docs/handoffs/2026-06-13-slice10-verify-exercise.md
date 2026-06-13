---
status: done
agent: slice10-builder-1
goal: "Slice 10: F4 exercise-history endpoint — re-scoped as a cache-vs-Hevy integrity check that respects the offline fence"
outcome: "`hevy-brain verify exercise <name>` cross-checks cache-derived per-exercise stats against Hevy's authoritative GET /v1/exercise_history/{id} and reports drift. New client method + analytics/reconcile.py + CLI subcommand. 264 offline tests (was 248), ruff clean. Live read-only run caught a wrong schema assumption (events-with-sets), fixed to the real one-entry-per-set shape; post-fix the cache reconciles exactly against the real account."
gotchas: "F4 was deliberately RE-SCOPED. As literally written (move per-exercise analytics onto the live endpoint) it breaks the 'vault rebuildable offline' fence and adds no new data — a full-sync cache already holds every set the endpoint returns. So the network call lives ONLY in the verify command; nothing else touches it. The real /v1/exercise_history/{id} response is a flat list under `exercise_history`, ONE ENTRY PER SET (top-level weight_kg/reps/workout_id/rpe/set_type), NOT sessions-with-nested-sets — so `sessions` = distinct workout_id, not list length. The first live run exposed the wrong assumption (445 entries, zero volume); reconcile.extract_server_sets now targets the real shape with an event-wraps-sets fallback. Drift tolerance: 0.5 kg absolute, or 0.1% of total volume (floored at 0.5 kg). A within-workout duplicate exercise entry can make cache times_performed exceed distinct server workout_ids by 1 (benign, documented)."
carry-on: "Extend C1 to guide-draft adherence (needs a Return/Redesign draft pushed AND trained first), or A4 session-quality patterns (time-of-day, RPE coverage, duration), or A5 bodyweight×strength trends; E4 ingestion stays an atlas-pipeline task"
---

# 13/06/2026 — Slice 10: F4 exercise-history integrity check

Last of section **F (write-back v2)**. F4 was marked *Optional / S* on the
roadmap, and on inspection it conflicts with the architecture as literally
written — so it was re-scoped (with Samrath's explicit sign-off) into the
version that delivers value without breaking a fence.

## The re-scope (why this isn't literal F4)

Per-exercise stats and PRs are derived **100% offline** from the cache
(`prs.exercise_histories` walks every cached workout); the cache holds every
set of every workout. `GET /v1/exercise_history/{id}` returns the *same* data
Hevy already gave us at sync time. So "move analytics onto the endpoint" would:
(1) put the network on the vault-build path — breaks "vault rebuildable
offline"; (2) cost ~1 call per trained exercise (~85) vs 0 today — not cheaper;
(3) add no new information. Samrath chose the **integrity-check** shape: keep
everything offline, and use the endpoint only to answer "has my cache drifted
behind Hevy?"

## Done (commit 55d4081, pushed)

1. **`api/client.py`** — `async_get_exercise_history(template_id)` (read-only).
2. **`analytics/reconcile.py`** (new, pure/offline):
   - `resolve_exercise(histories, name)` — case-insensitive; exact match wins,
     else unique substring; ambiguous → returns candidate list.
   - `extract_server_sets(payload)` — tolerant flatten to a list of set
     records; targets the real `exercise_history` flat-set shape, with an
     event-wraps-`sets` fallback; `[]` on unrecognised shape.
   - `aggregate_server(sets)` — sessions (distinct `workout_id`), best weight,
     best est-1RM (same Epley as the cache), total volume.
   - `compare(history, server)` — one row per metric; 0.5 kg / 0.1%-of-volume
     tolerance; `ok` flag.
3. **`cli.py`** — `verify exercise <name>` subcommand (network only here; cache
   load + name resolution happen before any session opens, so a bad name never
   touches the network). Exit 1 on drift. `guide`/`push`/`verify` group
   dispatch extracted to `_dispatch_*` helpers to keep `main()` under ruff's
   branch limit.
4. **Tests** — `tests/test_verify.py` (resolution, tolerant parsing of the real
   + fallback shapes, aggregate, clean-match, drift, tolerance scaling) +
   `test_api.py` endpoint test. 264 total (was 248).

## Process (ultracode)

No design panel — but a **mid-build design fork** surfaced (literal F4 breaks a
fence) and was put to Samrath via a question with a recommendation; he picked
the verify/audit shape. The **live read-only run was the verifier** and earned
its keep: the assumed schema (events with nested `sets`) was wrong — the first
run showed 445 entries with zero weight/volume but sessions=445, which is the
set count, not sessions. Dumped the real payload, found one-entry-per-set under
`exercise_history`, reworked the parser, re-verified.

## Verify

`python -m pytest tests -q` → **264 passed** (was 248) · `python -m ruff check
hevy_brain tests` → clean. All offline. **Live (read-only):** `verify exercise
"Incline Bench Press (Dumbbell)"` → 131 sessions / 84 kg / 96.27 e1rm /
185,262 kg, every row `ok` (cache matches Hevy) — derived from 445 real set
records. Name resolution verified live too (`"press"` → ambiguous candidate
list; a nonsense name → clean "no match", no network call).

## Decisions taken (SAMRATH.md §3 defaults + one §4-style fork)

- **§4 fork (asked):** literal F4 vs integrity-check vs skip → integrity-check,
  on Samrath's explicit choice (it conflicts with the offline fence).
- **Tolerance** 0.5 kg absolute / 0.1% of volume — Hevy stores 2dp; sub-kg gaps
  are rounding, not drift.
- **Four metrics** (sessions, best weight, best e1rm, total volume) — robustly
  comparable across both derivations. PR *count* is cache-only (the endpoint
  gives no PR events), so it's not reconciled.
- **`sessions` = distinct `workout_id`** on the server side (the list is per
  set). A within-workout duplicate entry can inflate the cache's count by 1 —
  documented, benign.

## Watch / gotchas

- The endpoint's response shape is now pinned in code + this handoff
  (one-entry-per-set under `exercise_history`). If a `verify` run ever prints
  "no recognisable history", Hevy changed the shape — re-dump and adjust
  `extract_server_sets`.
- `verify exercise` is the **only** offline-fence exception by design (explicit
  command, read-only). Do not let `reconcile` or the endpoint leak onto the
  vault/coach paths.
- `HevyBrain Coach` still pending first fire (next Sun 14/06 19:00 — tomorrow).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice10-verify-exercise.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — `logs\coach.log`
> / `Get-ScheduledTaskInfo`)? Build the next slice — candidates: **extend C1 to
> guide-draft adherence** (grade whether a pushed Return/Redesign draft was
> trained to its prescribed loads — needs a draft actually pushed AND trained
> first), **A4 session-quality patterns** (time-of-day, RPE coverage, duration
> trends), or **A5 bodyweight×strength ratio trends** (vault-local). Offline
> tests with fixtures, ruff clean, one slice, commit per coherent step, push at
> end, update HANDOFF + dated handoff + carry-on. Locked: explicit-push fence;
> vault rebuildable **offline** (the new `verify` command is the only
> read-only network exception — keep it that way); free tiers; read-only
> knowledge bridge (never write pipeline folders, never read sources/); repo
> private until key rotation. E4 stays an atlas-pipeline task. Do not
> re-litigate.
