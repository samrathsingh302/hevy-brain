---
status: done
agent: slice6-builder-1
goal: "Slice 6: F3 `hevy-brain push workout <file> --update` — fix a logged workout from its note"
outcome: "workout fix-up round-trip shipped: GET+PUT /v1/workouts/{id}, round-trippable workout notes (type: hevy-workout + full exercises spec), parse_workout_note + workout_diff on a shared _exercise_diff loop, CLI `push workout --update [--dry-run]`. RPE 6-10-in-halves validated (shared by create+update); times required on update; 204 offline tests (was 187), ruff clean; live read-only verified — unedited note = 'no changes', edited diff renders correctly, new GET endpoint works against the real account"
gotchas: "Workout notes now carry type: hevy-workout + is_private + description + the editable exercises spec in frontmatter — the whole vault was rebuilt (285 workout notes changed). RPE validation is now shared, so a planned-workout (create) note with an out-of-range RPE is now rejected too (intentional). Workout id comes from the note's hevy_id — no id arg (consistent with push routine). --dry-run only works with --update. NO live workout PUT yet — only dry-runs; first real edited push should still --dry-run first."
carry-on: "A1 progress charts / C1 coach memory / F4 exercise-history endpoint; E4 ingestion stays an atlas-pipeline task"
---

# 13/06/2026 — Slice 6: `push workout --update` (F3)

Completes the write-back trio (workout create + routine edit + **workout
fix-up**). Lets you correct a logged workout — typo'd weight, forgotten
set, missing RPE — by editing a draft of its note and pushing it back.

## Env check (carry-on item)

`HevyBrain Coach` has **still never fired** — expected. Today is Saturday
13/06; the first slot is Sunday 14/06 19:00. `Get-ScheduledTaskInfo`:
LastTaskResult `0x41303` (SCHED_S_TASK_HAS_NOT_RUN), NextRunTime
14/06/2026 19:00, no `logs\coach.log` yet. Nothing to fix; re-check after
Sunday evening. `HevyBrain Sync` continues healthy.

## Done (commits 62c0dfb + f77b3ac + 6125239, pushed)

1. **API client** (`62c0dfb`) — `async_get_workout(id)` +
   `async_update_workout(id, body)` (PUT, full replacement). 2 dispatch
   tests.
2. **Round-trippable workout notes** (`f77b3ac`):
   - `models.build_workout_record` now carries `is_private` and per-exercise
     `superset_id` through.
   - `vault/workouts.workout_exercises_spec` extracts the editable spec; the
     note frontmatter gains `type: hevy-workout`, `is_private`,
     `description` (when set), and the full `exercises` spec, plus a fix-up
     `[!info]` callout. Defaulting a missing set type to `normal` keeps an
     unedited draft an exact no-op.
3. **Parser + diff** (`f77b3ac`, `writeback/hevy_push.py`):
   - `parse_workout_note` → `(workout_id, {"workout": …})`. **RPE validated**
     to 6-10 in half-point steps (workout sets support RPE; routine sets do
     not). **start_time/end_time required** — a full-replacement PUT must
     never silently reset the logged session to "now".
   - `workout_diff`, `unwrap_workout`, `push_workout_update`.
   - Extracted a **shared `_exercise_diff` loop**; `routine_diff` was
     refactored onto it (behaviour identical, pinned by the existing routine
     tests). `_to_utc` normalises times so an unedited time never shows as a
     spurious diff (PyYAML loads a quoted ISO as a str, an unquoted one as a
     UTC datetime — both handled).
   - RPE validation is shared by the create (`parse_planned_workout`) and
     update parsers via `_parse_workout_set` + `_parse_workout_exercises`.
4. **CLI** (`6125239`) — `push workout <file> --update [--dry-run]`: GET →
   diff preview → PUT, with a no-changes short-circuit. Mirrors
   `push routine`. The id comes from the note's `hevy_id` (no id arg).
   `--dry-run` without `--update` is rejected (create has no diff).
5. **Tests**: round-trip no-op pinned three ways — unit (render→parse→diff),
   end-to-end through the real `build_vault`, and **live** against the real
   account. CLI dry-run/no-op/reject paths + argparse wiring covered.

## Verify

`python -m pytest tests -q` → **204 passed** (was 187) · `python -m ruff
check hevy_brain tests` → clean. All offline.

**Live (read-only — GET + diff only, nothing sent):**
- Unedited `2026-04-11` workout note, `--update --dry-run` → **"no changes —
  nothing to push"**. The real server payload, normalised the same way the
  notes are built, matches the parsed note exactly. (Also the first live
  exercise of the new `GET /v1/workouts/{id}`.)
- A Drafts copy with a bumped weight + added RPE + an extra set → diff
  rendered `sets 3 → 4` and `set 1: normal 20kg ×15 → normal 22.5kg ×15
  RPE 8.5`, then "Dry run — nothing sent". Draft deleted afterwards.

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Workout id from the note's `hevy_id`**, no separate id arg — consistent
  with `push routine`, and the note always carries it.
- **RPE validation shared** by create + update — it's a universal Hevy
  workout-set rule (6-10 in halves); validating both is correct, even though
  it slightly tightens the pre-existing create path.
- **start_time/end_time required on update** — PUT is full-replacement; a
  fallback-to-now would corrupt the session timestamp.
- **Server payload normalised via `build_workout_record`** (the canonical
  raw→record converter) before diffing, so the diff is apples-to-apples with
  how notes are generated.
- **Diff times normalised to UTC** before comparison so an unedited time is
  never a spurious diff.

## Watch / gotchas

- **The whole vault was rebuilt** — all 285 workout notes changed (new
  frontmatter). Expected; the vault is gitignored. Future `vault`/`full`
  runs are idempotent again.
- A **planned-workout (create) note with an out-of-range RPE is now
  rejected** (shared validation). Intended, but a behaviour change for the
  create path.
- **No live workout PUT has happened** — only dry-runs. The full-replacement
  PUT body for a real edit hasn't hit the server; first real edited push
  should still `--dry-run` first as usual (slice-5 precedent: the live
  dry-run is where surprises surface).
- Workout sets can carry `rpe`; the diff/spec keep it. Routine sets still
  reject RPE (unchanged).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice6-workout-fixup.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 yet (first ever run — check
> `logs\coach.log` / `Get-ScheduledTaskInfo`)? The write-back trio (workout
> create + routine edit + workout fix-up) is now complete. Build the next
> slice — recommended: **A1 progress charts** (Mermaid xychart = zero deps:
> weekly volume + e1RM trends in the Dashboard/Reviews) or **C1 coach
> memory** (briefing includes last recommendations + a computed "was it
> followed?") or **F4** (swap some cache-side analytics to `GET
> /v1/exercise_history/{id}`). Offline tests with fixtures, ruff clean, one
> slice, commit per coherent step, push at end, update HANDOFF + dated
> handoff + carry-on. Locked: explicit-push fence; free tiers; read-only
> knowledge bridge (never write pipeline folders, never read sources/); repo
> private until key rotation. E4 (ingest programming episodes) stays an
> atlas-pipeline task. Do not re-litigate.
