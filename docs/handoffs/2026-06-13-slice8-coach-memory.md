---
status: done
agent: slice8-builder-1
goal: "Slice 8: C1 coach memory — the coach briefing carries a computed 'since your last briefing' adherence recap"
outcome: "Coach memory shipped: each coach run persists an objective focus snapshot to meta['coach_focus'] (consistency, push/pull ratio, flagged plateaus + their est-1RM); the next run grades those against newer logged workouts and renders a '## Since your last briefing' recap (plateaus improved/held/regressed/can't-grade, sessions + PRs since, consistency, push/pull movement). Honest by construction — grades the objective situation, never Claude's below-marker prose. 239 offline tests (was 223), ruff clean; live free-coach run persisted the first snapshot (no recap on a first run, as designed). Design from a 3-approach panel; diff adversarially reviewed."
gotchas: "The recap grades the SITUATION the advice addressed (plateau e1RMs, frequency, push/pull), NOT Claude's written recommendations — those are free text below the %% hevy-brain:end %% marker, opaque to hevy-brain. The note says so (italic subhead + [!note]). The free coach path now calls store.save() (it previously never did) to persist the snapshot. Grade-before-record: the recap compares against the PRIOR snapshot, recorded after. A first-ever run shows no recap. Same-day re-runs grade nothing (no workouts logged after today's snapshot). Snapshots are keyed by exercise TITLE — a rename reads as 'can't grade'. Scope is coach only; guide-draft adherence is a deliberate future item."
carry-on: "A2 year-in-review note (totals, PRs, best month, streaks) or F4 exercise-history endpoint or B-side guide-draft adherence (grade whether pushed return/redesign drafts were trained to); E4 ingestion stays an atlas-pipeline task"
---

# 13/06/2026 — Slice 8: C1 coach memory

Second of the roadmap's **C. Coach upgrades**. Closes the loop: the coach now
remembers what the data said to watch and shows, on the next run, how those
objective metrics actually moved.

## Done (commit 7ae9930, pushed)

1. **`coach/memory.py`** (new) — the focus snapshot + adherence recap:
   - `build_focus_snapshot` captures, per run, only machine-derived numbers:
     `sessions_last_7d`, `current_streak_days`, `push_pull_ratio`,
     `plateau_weeks`, and the flagged `plateaus` with their `e1rm_kg`. No
     Claude prose is ever stored.
   - `record_focus` / `latest_focus` keep a bounded history (last 12) in
     `store.meta["coach_focus"]` (sibling of `coach_calls`).
   - `grade_focus` re-derives the metrics from workouts logged **after** the
     prior snapshot and renders `## Since your last briefing`:
     per-plateau **improved / held / regressed / can't-grade** (±0.5 kg
     tolerance), sessions-since, new PRs since, consistency trend, push/pull
     movement. Returns None on a first run (no orphan heading).
2. **Wiring** (`advisor.py` + `cli.py`) — `render_briefing` and
   `render_coach_note` take an optional `recap`; `_cmd_coach` grades the prior
   snapshot, shows the recap, then records this run's snapshot and
   `store.save()`s on **both** paths (the free path previously never saved).
   Grade-before-record so a run never grades itself.
3. **Honesty** — the recap's italic subhead and a `[!note]` callout state it
   grades the objective situation the advice addressed, not the written
   recommendations (which hevy-brain can't read below the marker). Every line
   is an observed-data statement; untrained lifts are "can't grade", never
   silently scored.

## Process (ultracode) — workflows used

- **Design panel** (3 approaches): objective-snapshot vs structured-capture vs
  minimal-recap. All three converged on the only honest mechanism (grade
  hevy-brain's own signals, never parse Claude's prose). Synthesised the
  scorecard (A) + momentum recap (C), scoped to coach, dropped the brittle
  read-back-prior-note "Focus:" echo.
- **Adversarial review** (4 lenses → per-finding verification): no
  blockers/majors survived. Folded in: hardened `grade_focus` against a
  malformed/old-schema `meta.json` (the "coach never breaks" doctrine — a
  corrupt snapshot degrades to None / skipped lines, never crashes the
  unattended Sunday run) + a best-effort wrapper in `_cmd_coach`; added tests
  for the held verdict, consistency trend words, the push/pull line, the
  malformed snapshot, and `--api` persistence. The api-path "save before note
  write" ordering was **kept** (it must count the billed call regardless of a
  later note-write failure — the proposed "fix" would regress budget
  accounting).

## Verify

`python -m pytest tests -q` → **239 passed** (was 223) · `python -m ruff
check hevy_brain tests` → clean. All offline. **Live (read-only vs Hevy):**
`hevy-brain coach` (free) wrote the briefing, loaded 83 cited claims, and
persisted the first `coach_focus` snapshot
(`{path: free, sessions_last_7d: 0, push_pull_ratio: null, plateaus: []}` —
honestly reflecting the lapse); no recap on the first run, as designed. The
recap will render on the next coach run that has workouts logged after that
snapshot.

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Grade the objective situation, never Claude's prose** — the only honest
  option given free-path recs are opaque; explicit in the note.
- **Coach only** — `guide return/redesign` drafts are structured and a natural
  future home for true plan-adherence grading; out of scope for C1.
- **ISO dates** in the recap (matches the existing coach notes).
- **±0.5 kg plateau tolerance** so float noise doesn't flap improved/regressed.
- **Snapshot keyed by exercise title**; a rename reads as "can't grade"
  (honest — it genuinely wasn't trained under that name).

## Watch / gotchas

- The **free path now saves `meta`** (to persist the snapshot) — benign, but
  it's a behaviour change from "free path never wrote the cache".
- **Same-day re-runs** grade nothing (no workouts logged after today's
  snapshot) and render "nothing to grade yet" — correct, not a bug.
- Snapshots are capped at the last 12; grading always uses the most recent.
- `HevyBrain Coach` (Sundays 19:00) will now persist a snapshot each week; the
  first real recap appears the **second** Sunday it fires (or the next manual
  run after one is recorded).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice8-coach-memory.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — `logs\
> coach.log` / `Get-ScheduledTaskInfo`)? It will now also persist a
> `coach_focus` snapshot to the cache. Build the next slice — recommended:
> **A2 year-in-review** note (totals, PRs, best month, streaks; self-contained,
> like A1) or **F4** (swap some cache-side analytics to `GET
> /v1/exercise_history/{id}`) or extend C1 to **guide-draft adherence** (grade
> whether a pushed Return/Redesign draft was actually trained to its loads).
> Offline tests with fixtures, ruff clean, one slice, commit per coherent step,
> push at end, update HANDOFF + dated handoff + carry-on. Locked: explicit-push
> fence; free tiers; read-only knowledge bridge (never write pipeline folders,
> never read sources/); repo private until key rotation. E4 (ingest programming
> episodes) stays an atlas-pipeline task. Do not re-litigate.
