---
status: done
agent: slice13-builder-1
goal: "Slice 13: A5 strength-to-bodyweight ratio trends — relative strength on the (private) Body Log"
outcome: "New analytics/strength_ratio.py pairs bodyweight (measurements) with est-1RMs (histories): latest ratios for the top weighted lifts + a relative-strength trend for the strongest, rendered on the Body Log note only. 313 offline tests (was 302), ruff clean. Live rebuild touched only the Body Log (idempotent); verified against the real account."
gotchas: "Body data is PRIVATE — these sections live on the Body Log note only, never the Dashboard or anything published (locked CV-readiness decision). render_body_log now takes histories (build.py call updated) — any other caller must pass it. Measurement `date` is a STRING (YYYY-MM-DD); strength_ratio parses it to date and drops unparseable/no-weight entries. ratio_trend uses best est-1RM AS OF each measurement date (max over sessions <= that date), so the trend reflects relative strength at the time, and dates before the lift's first session are skipped (no e1RM yet). top_ratios excludes bodyweight-only lifts (best_e1rm_kg == 0) and tie-breaks on title for determinism. The real measurement set is sparse and clustered mid-2025, so the trend table shows 2025 dates — that's the data, not a bug."
carry-on: "A6 Dataview/Bases starter pack (Hevy/Queries.md), or A3 lapse-detection nudge (dashboard/review callout after N quiet days); E4 ingestion stays an atlas-pipeline task. Slice 12's capture path still wants a real pushed+trained guide draft for full live proof."
---

# 13/06/2026 — Slice 13: A5 strength-to-bodyweight ratios

Fifth of section **A. Insights**, and the last of the readily-buildable A-items
that need no new ingestion. Relative strength — strength *for your size* — from
data already in the cache.

## Done (commit 43ae67a, pushed)

1. **`analytics/strength_ratio.py`** (new, pure/offline):
   - `bodyweight_points(measurements)` — sorted `(date, weight_kg)`, dropping
     entries with no weight or an unparseable date.
   - `latest_bodyweight(measurements)` — most recent bodyweight, or None.
   - `top_ratios(histories, bodyweight, limit=5)` — top weighted lifts by
     est-1RM with their ×bodyweight ratio; bodyweight-only lifts excluded;
     title tiebreak for determinism; `[]` when bodyweight is missing/zero.
   - `best_e1rm_as_of(history, cutoff)` — best est-1RM from sessions on/before a
     date (0 if none).
   - `ratio_trend(history, measurements, limit=8)` — per recent measurement
     date, pair bodyweight with the est-1RM as of that date; skip pre-first-
     session dates; return the most recent `limit` points.
2. **`vault/dashboards.py`** — `_strength_to_bodyweight_lines(measurements,
   histories)` renders the latest ratios table + a relative-strength trend for
   the strongest lift (returns `[]` when nothing to show); `render_body_log`
   now takes `histories` and appends the block.
3. **`vault/build.py`** — passes `histories` into `render_body_log`.
4. **Tests** — `tests/test_strength_ratio.py` (11): bodyweight points
   sort/drop, latest, ratios (compute/order/exclude-bodyweight/limit/no-BW/
   tiebreak), best-as-of, trend (pair + skip-pre-session + limit).

## Process

No design panel (clear derived insight). Key decision: **Body Log only** — the
locked CV decision keeps bodyweight off anything published, so unlike A4
(Dashboard) this private signal stays on the private note. Built inline,
mirroring the existing Body Log table style.

## Verify

`python -m pytest tests -q` → **313 passed** (was 302) · `python -m ruff check
hevy_brain tests` → clean. **Live:** `hevy-brain vault` re-rendered **only** the
Body Log (0 other notes). At 87.7 kg bodyweight: top ratio Shrug (Cable)
217.7 kg = 2.48×, then Seated Row 1.78×, Leg Extension 1.60×. Relative-strength
trend for Shrug (Cable): 2.54× → 2.48× across mid-2025 measurement dates as
bodyweight rose 85.6 → 87.7 kg with est-1RM flat — an honest "got heavier, not
relatively stronger" read.

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Body Log only, never published** — bodyweight is private (locked decision).
- **Top lifts by est-1RM** (weighted only) — relative strength is about loaded
  lifts; bodyweight movements have no external-load ratio.
- **est-1RM *as of* each measurement date** for the trend — relative strength
  at the time, not today's best back-projected.
- **limit 5 ratios / 8 trend points**, hardcoded — S-sized, always-on like the
  rest of the Body Log; no new config.

## Watch / gotchas

- `render_body_log` signature changed (now needs `histories`).
- Measurement `date` is a string — parsed defensively; bad/empty dropped.
- The real measurement set is sparse + mid-2025, so the trend shows 2025 dates.
  Logging more bodyweight entries will extend it forward automatically.
- `HevyBrain Coach` still pending first fire (next Sun 14/06 19:00 — tomorrow).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice13-strength-ratio.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — `logs\coach.log`
> / `Get-ScheduledTaskInfo`)? Build the next slice — candidates: **A6
> Dataview/Bases starter pack** (`Hevy/Queries.md` — ready-made queries over the
> note frontmatter), or **A3 lapse-detection nudge** (a dashboard/review callout
> after N quiet days, feeding `guide return`). Optionally close slice 12's live
> gap: push a guide draft, train it, then `coach`. Offline tests with fixtures,
> ruff clean, one slice, commit per coherent step, push at end, update HANDOFF +
> dated handoff + carry-on. Locked: explicit-push fence; vault rebuildable
> **offline** (only `verify` makes a read-only network call); free tiers;
> read-only knowledge bridge (never write pipeline folders, never read
> sources/); **bodyweight/body data stays off anything published**; repo private
> until key rotation. E4 stays an atlas-pipeline task. Do not re-litigate.
