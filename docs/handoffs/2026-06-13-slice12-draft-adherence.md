---
status: done
agent: slice12-builder-1
goal: "Slice 12: extend C1 coach memory to guide-draft adherence — grade whether a pushed Return/Redesign draft was trained to its prescribed loads"
outcome: "New coach/adherence.py: a guide-draft push records an objective prescription (per-exercise top-set load by template_id + push date) into meta; a later coach run grades it from workouts trained AFTER the push (on/under/above target, trained/prescribed count, avg load %). Wired into push routine (capture) + coach (grade, folded into the recap). 302 offline tests (was 285), ruff clean. grade_target verified live read-only on the real account; capture-on-push not exercised live (no pushed+trained draft yet, no unprompted push)."
gotchas: "The routine PUT body keys exercises by exercise_template_id only — NO exercise title/name (parse_routine_note drops `name`). So the target stores template_id + top_weight + sets, and grade_target resolves the display label at grade time from store.exercise_templates (falls back to the template_id). Capture happens ONLY on a successful, non-dry-run push of a routine whose title starts with `Return Week 1` or `Redesign` (vault.drafts RETURN_PREFIX/REDESIGN_PREFIX) — a redesign draft pushed UNEDITED is a no-op (no diff → push short-circuits → no target). Capture is best-effort: the push has already landed, so a meta-save failure must never read as a push failure. grade_target has NO `today` param (graded relative to push date + the records). PLR0912: grade_target was 1 branch over — per-item grading extracted to _grade_item. Targets accumulate forward only: a push from BEFORE this feature has no target (adherence tracking starts now)."
carry-on: "A5 bodyweight×strength ratio trends (vault-local), A6 Dataview/Bases starter pack, or A3 lapse-detection nudge; E4 ingestion stays an atlas-pipeline task. To prove the capture path live: push a guide draft (push routine), train it, then run coach."
---

# 13/06/2026 — Slice 12: C1 extension — guide-draft adherence

Asked for directly ("extend c1"). Extends C1 coach memory (slice 8) from
grading the objective *situation* to grading a specific *prescription*: did a
pushed comeback/redesign draft actually get trained to its loads?

## The design (why capture at push time)

C1's philosophy: snapshot an objective signal when an action happens, grade it
later against real data, never judge the prose. Applied here:
- **A guide draft prescribes loads.** When `push routine` PUT-replaces the
  routine, the body carries the exact prescribed sets (by
  `exercise_template_id` — Hevy's PUT schema has no per-exercise title).
- **Capture at push time** → exact push date + prescription into
  `meta["draft_adherence"]`. Forward-looking: pushes before this feature have
  no target, so adherence tracking starts now.
- **Grade at coach time** → only workouts trained *after* the push count; the
  trained top set is compared to the prescribed top set per exercise.

## Done (commit 3d5c1b8, pushed)

1. **`coach/adherence.py`** (new):
   - `draft_kind(title)` — return / redesign / None (off `RETURN_PREFIX` /
     `REDESIGN_PREFIX`).
   - `build_target(body, today)` — prescription from a PUT body (top-set weight
     per exercise by template_id; bodyweight → `top_weight_kg None`); None when
     not a guide draft or no usable exercises.
   - `record_target` / `latest_target` — bounded meta history, tolerant of
     garbage.
   - `grade_target(target, records, *, templates)` — "Draft adherence" recap:
     per-exercise on/under/above target (95% / 105% bands), trained/prescribed
     count, average load %; honest "not trained yet" (per lift and overall).
     `_grade_item` does one exercise (keeps the branch count under the lint cap).
2. **`cli.py`**:
   - `_track_draft_adherence(config, body)` + a call after a successful
     non-dry-run push in `_cmd_push_routine` (best-effort; OSError on save is
     logged, never raised).
   - `_cmd_coach` grades the latest target and folds the recap in next to the
     C1 "since your last briefing" block (best-effort try/except — the
     unattended scheduled coach must never break).
   - `from typing import Any` added (used by the new helper's annotation).
3. **Tests** — `tests/test_adherence.py` (17): draft_kind, build_target
   (weights / non-draft / bodyweight / empty), record/latest (+bounded
   +garbage), grade (none / no-sessions-since / on+not-trained / under+above /
   only-after-push / bodyweight / malformed-skipped).

## Process

No design panel (clear extension of an existing pattern). Flagged up front: the
feature is buildable now but **end-to-end live verification is partial** — the
`upper` Return draft was pushed in slice 4 but predates this feature (no
target), and the current lapse means nothing has been pushed-and-trained since.
Caught during the build: the PUT body has no exercise titles (label resolved
from templates at grade time); the unused `today` param (removed); a 1-over
branch count (extracted `_grade_item`).

## Verify

`python -m pytest tests -q` → **302 passed** (was 285) · `python -m ruff check
hevy_brain tests` → clean. **Live (read-only):** built a target from a real
cached routine (`push 1`, 6 exercises), backdated the push, and graded against
real logged workouts — 6/6 trained, Incline Bench 84 vs 84 kg = on target
(100%), several above target, Hanging Leg Raise (bodyweight) correctly not
load-graded, avg load 123%. Proves `grade_target` runs on real data shapes and
produces honest verdicts.

## Watch / gotchas

- **Capture path unproven live.** First real use: `push routine` a guide draft,
  train it, then `coach`. Until then only the grade path is live-verified.
- Adherence is keyed by `exercise_template_id`; the display name comes from
  `store.exercise_templates` at grade time (falls back to the id if absent).
- A redesign draft pushed unedited records no target (no diff → no push).
- `HevyBrain Coach` still pending first fire (next Sun 14/06 19:00 — tomorrow);
  it will now also surface a draft-adherence recap once a target exists.

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice12-draft-adherence.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — `logs\coach.log`
> / `Get-ScheduledTaskInfo`)? Build the next slice — candidates: **A5
> bodyweight×strength ratio trends** (vault-local: bodyweight from measurements
> × top lifts), **A6 Dataview/Bases starter pack** (`Hevy/Queries.md`), or
> **A3 lapse-detection nudge** (dashboard/review callout after N quiet days).
> Optionally, to finally prove slice 12's capture path live: push a guide draft
> (`push routine`), train it, then run `coach`. Offline tests with fixtures,
> ruff clean, one slice, commit per coherent step, push at end, update HANDOFF +
> dated handoff + carry-on. Locked: explicit-push fence; vault rebuildable
> **offline** (only `verify` makes a read-only network call — keep it that way);
> free tiers; read-only knowledge bridge (never write pipeline folders, never
> read sources/); repo private until key rotation. E4 stays an atlas-pipeline
> task. Do not re-litigate.
