---
status: done
agent: slice11-builder-1
goal: "Slice 11: A4 session-quality patterns — time-of-day, RPE coverage, duration trends on the Dashboard"
outcome: "New 'Session quality' Dashboard block: when you train (part-of-day distribution + modal time), RPE logging coverage over working sets, and a session-duration summary with a recent-vs-prior trend. New pure/offline analytics/session_quality.py; rendered into the Dashboard after Muscle balance. 285 offline tests (was 264), ruff clean. Live rebuild touched only the Dashboard (idempotent) — verified against the real account."
gotchas: "Cache set dicts use the key `type` (value `warmup`), NOT `set_type` (that's the exercise_history endpoint's field) — rpe_coverage keys off `s.get('type') == 'warmup'` to exclude warm-ups, and `s.get('rpe')` (halves, None when absent). Time-of-day uses each workout's recorded start hour, which is tz-aware as Hevy stored it (effectively UTC) — for a UK user in summer that's ~1h behind local civil time; coarse enough for morning/evening habits, documented in the module. Duration excludes sessions with no end time (duration_seconds 0) so a missing end never reads as a 0-min session — BUT a genuine sub-minute session (e.g. ~30s) still rounds to '0 min' in the range (the live Dashboard shows 'range 0–147'); that 0 is real data, not a bug. Section is always-on (no config) like Muscle balance; whole block omitted when there's nothing to show."
carry-on: "Extend C1 to guide-draft adherence (needs a Return/Redesign draft pushed AND trained first), or A5 bodyweight×strength ratio trends (vault-local), or A6 Dataview/Bases starter pack; E4 ingestion stays an atlas-pipeline task"
---

# 13/06/2026 — Slice 11: A4 session-quality patterns

Fourth of section **A. Insights**. Lightweight habit-level signals that round
out the Dashboard: *when* you train, how disciplined your RPE logging is, and
how long sessions run.

## Done (commit eb7036f, pushed)

1. **`analytics/session_quality.py`** (new, pure/offline):
   - `part_of_day(hour)` — Early morning / Morning / Afternoon / Evening /
     Night (Night wraps midnight).
   - `time_of_day_counts(records)` — workout counts per part of day, in time
     order, empty buckets omitted.
   - `rpe_coverage(records)` — `{working_sets, rpe_sets, coverage}` over working
     sets only (warm-ups excluded); `coverage` is `None` when there are none.
   - `duration_summary(records, recent_n=10)` — avg / median / longest /
     shortest, plus `recent_avg` vs `prior_avg` (last `recent_n` sessions vs the
     `recent_n` before) for a trend; sessions with no end time excluded.
   - `session_quality(records)` — rolls up the three views.
2. **`vault/dashboards.py`** — `_session_quality_lines(records)` renders the
   block (returns `[]` when nothing to show), inserted into `render_dashboard`
   after Muscle balance, before Recent PRs.
3. **Tests** — `tests/test_session_quality.py` (21): part-of-day boundaries,
   bucket/omit/order, warm-up exclusion, coverage `None`, duration zero-exclusion
   + recent/prior trend + too-few-sessions, the roll-up.

## Process (ultracode)

No design panel (A4 has no product fork — it's "summarise habits"). Built inline
against the existing Dashboard surface, mirroring the Muscle-balance section's
shape and the redesign module's warm-up convention. Caught during the build: the
60-minute end-time test string was an invalid time (`T10:60:00`) — fixed before
it shipped; and the warm-up key is `type`, not the endpoint's `set_type`.

## Verify

`python -m pytest tests -q` → **285 passed** (was 264) · `python -m ruff check
hevy_brain tests` → clean. All offline; idempotency covered by the existing
whole-build test. **Live:** `hevy-brain vault` re-rendered **only** the
Dashboard (0 other notes) — Session quality reads: When Morning 10 · Afternoon
31 · Evening 209 · Night 35 (most often **Evening**); RPE logged **28%** of
working sets (1,189/4,249); Duration avg **63 min** (median 57, range 0–147),
recent 57 min (up).

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Dashboard block, not a new note** — habit-level signal belongs with the
  other patterns; no new note lifecycle (S-sized).
- **Always-on, no config** — pure derived text, no cost; consistent with Muscle
  balance. (Charts are config-gated because they're heavier Mermaid; this isn't.)
- **RPE coverage over working sets** (warm-ups excluded) — warm-ups legitimately
  carry no RPE, so including them would understate discipline.
- **Time-of-day from the recorded start hour** (tz as stored ≈ UTC) — accepted
  the ~1h UK-summer skew; documented. Coarse buckets, not exact times.
- **recent_n = 10** for the duration trend — hardcoded; a session-count window,
  lapse-agnostic.

## Watch / gotchas

- `range 0–147`: the `0` is a genuine sub-minute logged session rounding down,
  not a missing-end artefact (those are excluded). Honest; the avg/median carry
  the real signal.
- Time-of-day hour is UTC-ish (see decisions) — don't read it as exact local
  clock time.
- The block is always-on; if it ever needs gating, follow the `[charts]`
  config pattern.
- `HevyBrain Coach` still pending first fire (next Sun 14/06 19:00 — tomorrow).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice11-session-quality.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — `logs\coach.log`
> / `Get-ScheduledTaskInfo`)? Build the next slice — candidates: **extend C1 to
> guide-draft adherence** (grade whether a pushed Return/Redesign draft was
> trained to its prescribed loads — needs a draft actually pushed AND trained
> first), **A5 bodyweight×strength ratio trends** (vault-local: bodyweight from
> measurements × top lifts), or **A6 Dataview/Bases starter pack**
> (`Hevy/Queries.md`). Offline tests with fixtures, ruff clean, one slice,
> commit per coherent step, push at end, update HANDOFF + dated handoff +
> carry-on. Locked: explicit-push fence; vault rebuildable **offline** (only
> `verify` makes a read-only network call — keep it that way); free tiers;
> read-only knowledge bridge (never write pipeline folders, never read
> sources/); repo private until key rotation. E4 stays an atlas-pipeline task.
> Do not re-litigate.
