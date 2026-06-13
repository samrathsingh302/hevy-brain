---
status: done
agent: slice9-builder-1
goal: "Slice 9: A2 year-in-review — one summary note per calendar year of training"
outcome: "Year-in-review shipped: Reviews/<year> Year in Review.md per year — totals (sessions/volume/reps/active days/longest streak), a 12-bar monthly-volume Mermaid chart, best month, muscle balance + push/pull, most-trained lifts, and that year's PRs. 248 offline tests (was 239), ruff clean, idempotent; live rebuild wrote 4 year notes (2023-2026), 2024 verified (125 sessions / 705,293 kg / streak 6 / 274 PRs, all consistent). Design built inline (no product fork); diff adversarially reviewed."
gotchas: "Year notes are auto-generated on every vault/full run, one per calendar year with workouts (no config, no command). Reuses A1's chart renderer (monthly_volume_chart = 12 bars, hardcoded month labels for byte-identical rebuilds). Longest streak is measured WITHIN the calendar year — a run crossing 31 Dec/1 Jan is counted in each year separately (documented at the call site). Top-exercise 'sessions' now counts distinct workouts (a lift logged twice in one workout is one session). patterns.volume_by_group gained a group-name tiebreak on exact volume ties — touched a shared function, but the live rebuild re-rendered 0 existing notes (no real ties), so no churn."
carry-on: "F4 exercise-history endpoint, or extend C1 to guide-draft adherence, or A4 session-quality patterns (time-of-day, RPE coverage, duration); E4 ingestion stays an atlas-pipeline task"
---

# 13/06/2026 — Slice 9: A2 year-in-review

Third of the roadmap's **A. Insights**. A polished annual summary per year of
training — the kind of artefact that reads well both in the vault and on a CV.

## Done (commit ce4d6cc, pushed)

1. **`vault/yearreview.py`** (new):
   - `render_year_review(year, year_records, histories, today, ...)` → the
     managed note: headline totals (sessions, active days, total volume, reps,
     longest streak), an embedded **monthly-volume chart**, best month, muscle
     balance (volume share per group + push/pull ratio), top-5 most-trained
     lifts by volume (with distinct-workout session counts), and that year's
     PRs (count + the 10 most recent + an "…and N more").
   - `generate_year_reviews(...)` writes one `Reviews/<year> Year in Review.md`
     per calendar year that has workouts.
2. **`charts.monthly_volume_chart` / `monthly_volume_points`** — a 12-bar
   (Jan–Dec) bar chart for a year; untrained months are empty bars; month
   labels are a hardcoded English tuple (locale-independent → byte-identical
   rebuilds). Reuses A1's `mermaid_xychart` + `chart_section` (a zero-volume
   year → no chart, no orphan heading).
3. **`build.py`** wires `generate_year_reviews` into `build_vault`.
4. **`patterns.volume_by_group`** now breaks exact volume ties by group name —
   it was the only ranking in the codebase without a stable secondary key, so
   muscle-balance ordering no longer depends on input order.

## Process (ultracode)

No design panel — A2 has no product fork (it's "summarise a year"), so I built
inline against a clear design. **Adversarial review** (4 lenses → per-finding
verification): no blockers/majors; two "verified clean" passes independently
confirmed idempotency (byte-identical even from a reshuffled cache) and
determinism. Folded in: the top-exercise **session over-count** (counted per
exercise *entry*, not per workout — a lift logged twice in one session read as
"2 sessions"; now de-duped per workout), the `volume_by_group` tiebreak, a
docstring/comment on the intentional within-year streak clip, and tests for
the tie-breaks + the zero-volume-year chart omission.

## Verify

`python -m pytest tests -q` → **248 passed** (was 239) · `python -m ruff
check hevy_brain tests` → clean. All offline; idempotency covered by the
existing whole-build test (now includes year reviews). **Live:** `hevy-brain
vault` wrote **4** year notes (2023–2026) and re-rendered **0** other notes
(the shared-tiebreak change hit no real ties). Spot-checked 2024: 125
sessions, 705,293 kg, longest streak 6, January the best month (matches the
chart's tallest bar), push/pull 1.60, top lift Seated Row, 274 PRs.

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **One note per calendar year** with workouts (no config, no count cap) —
  the full journey is the value; bounded by reality (4 years).
- **Longest streak within the year** — a New Year–spanning run counts in each
  year separately (documented at the call site).
- **Top-exercise sessions = distinct workouts** (de-duped within a workout).
- **Month labels hardcoded English** (no `strftime`) for locale-independence /
  determinism.
- **Embedded monthly chart** (12 bars), not weekly (52 bars would be an
  unreadable label smear — the A1 legibility lesson).

## Watch / gotchas

- Year notes regenerate on every `vault`/`full` run; the current (partial)
  year shows trailing empty month bars — intended.
- `patterns.volume_by_group` is shared (dashboard + weekly/monthly reviews +
  year reviews); the tiebreak change re-rendered 0 notes live, but a future
  dataset with an exact group-volume tie would re-order that note once.
- `HevyBrain Coach` still pending first fire (Sat 13/06; next 14/06 19:00).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice9-year-in-review.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — `logs\
> coach.log` / `Get-ScheduledTaskInfo`)? Build the next slice — recommended:
> **F4** (swap some cache-side analytics to `GET /v1/exercise_history/{id}`),
> **extend C1 to guide-draft adherence** (grade whether a pushed
> Return/Redesign draft was trained to its loads — needs a draft actually
> pushed first), or **A4 session-quality patterns** (time-of-day, RPE
> coverage, duration trends). Offline tests with fixtures, ruff clean, one
> slice, commit per coherent step, push at end, update HANDOFF + dated handoff
> + carry-on. Locked: explicit-push fence; free tiers; read-only knowledge
> bridge (never write pipeline folders, never read sources/); repo private
> until key rotation. E4 (ingest programming episodes) stays an atlas-pipeline
> task. Do not re-litigate.
