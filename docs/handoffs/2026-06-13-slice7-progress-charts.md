---
status: done
agent: slice7-builder-1
goal: "Slice 7: A1 progress charts — Mermaid xychart volume + e1RM trends in the vault"
outcome: "Zero-dep progress charts shipped: a 12-week weekly-volume bar on the Dashboard and a per-exercise est-1RM bar (last 10 loaded sessions), rendered as Mermaid xychart-beta (native in Obsidian). Config-gated via a new [charts] block. 223 offline tests (was 204), ruff clean; vault rebuilt and charts verified against the real account. Design de-risked and the diff adversarially reviewed via multi-agent workflows before commit."
gotchas: "Both charts are BARs on purpose — Mermaid LINE series can render blank under some Obsidian themes (stroke-width 0), and bars don't imply false continuity across irregular sessions. The weekly window is contiguous (untrained weeks = 0 bars) so a lapse reads honestly — Samrath's Dashboard now shows one bar (W15 ≈ 11/04) and zeros after. Labels are ISO-native (W## weekly, mm-dd per-exercise) to match the vault; NOT British dd/mm. Known cosmetic nit: two LOADED sessions of one exercise on the same day yield a duplicate mm-dd x-label (real example: Incline Bench 01-24 ×2) — both bars are real, left as-is. Rebuild touched only Dashboard + 85 exercise notes (workouts untouched)."
carry-on: "C1 coach memory (last recs + 'was it followed?') or F4 exercise-history endpoint or A2 year-in-review; E4 ingestion stays an atlas-pipeline task"
---

# 13/06/2026 — Slice 7: A1 progress charts

First of the roadmap's **A. Insights** ideas. Charts the data that already
exists (weekly volume, per-exercise estimated 1RM) directly into the notes,
with zero new dependencies — Obsidian renders `mermaid` blocks natively.

## Done (commit 3a75d7c, pushed)

1. **`vault/charts.py`** — a deterministic Mermaid `xychart-beta` renderer +
   point builders:
   - `weekly_volume_chart` — a **contiguous** last-12-week bar window anchored
     at this week, untrained weeks filled as 0 bars (a training gap reads as
     elapsed time, not compressed bars), ISO-week "W##" labels.
   - `e1rm_chart` — per-exercise bar over the last 10 **loaded** sessions
     (`best_e1rm_kg > 0`, so bodyweight/cardio exercises get no chart),
     "mm-dd" labels widening to "yy-mm-dd" only when the window spans years,
     y-axis a padded nearest-5 band so a small strength trend stays visible.
   - Both are **bars** (see gotchas). Guards: non-finite points dropped (a
     stray NaN can never abort the build), `<2` points / all-zero → no chart,
     flat series never collapses the axis, `_clean()` strips quotes / brackets
     / commas / newlines from title, y-label and every x-label.
   - `chart_section()` returns `[]` for a `None` chart, so a missing chart
     never leaves an orphan heading.
2. **`[charts]` config** — `enabled` (default true), `volume_weeks` (12),
   `e1rm_points` (10); `config.example.toml` updated. Disabled → `weeks/points
   = 0` → both chart and heading omitted.
3. **Wiring** — Dashboard volume trend (`render_dashboard`) + per-exercise
   e1RM trend (`render_exercise_note`), threaded from `build.py`. The
   monthly-review chart was **deliberately cut** (4–5 bars, redundant with the
   note's prose — low value-to-clutter).
4. **Tests** — `tests/test_charts.py` (20 unit tests: guards, label formats,
   injection cleaning, builders) + build-level wiring tests (renders /
   disabled-omits / enabled-but-`None` leaves no orphan heading / idempotent).
   **223 passed** (was 204), ruff clean.

## Process (ultracode) — workflows used before commit

- **De-risk workflow** (3 agents, parallel): verified Mermaid `xychart-beta`
  is supported (v10.6.0+; Obsidian ships 11.x) and the planned output is
  valid; correctness + UX critiques. It caught a **build-aborting blocker**
  (`int(NaN)` in the value formatter) and drove real changes: ISO labels over
  dd/mm, contiguous zero-filled weekly window, bars over lines, e1rm_points
  15→10, padded nearest-5 e1RM band, monthly chart cut.
- **Adversarial review workflow** (4 review lenses → per-finding skeptic
  verification, 11 agents): **no blockers/majors survived**; one agent gave a
  full clean bill (reproduced every fix, 223 pass, ruff clean). The confirmed
  findings were all test-hardening (the code was correct, the invariants just
  weren't all pinned) — folded in: comma-stripping in `_clean`
  (defence-in-depth for the x-axis delimiter), an F7 render-boundary test
  (enabled-but-`None` → no heading), x-label/y-label clean assertions, NaN
  label/value co-deletion assertion, disabled-dashboard heading assertion.

## Verify

`python -m pytest tests -q` → **223 passed** · `python -m ruff check
hevy_brain tests` → clean. All offline. **Live (read-only):** `hevy-brain
vault` rebuilt 86 notes (Dashboard + 85 exercise notes; workouts untouched).
Spot-checked the real output: Dashboard shows W13–W24 with a single bar at W15
(≈ the 11/04 last workout) and zeros after — the lapse, honestly. Incline
Bench note shows a 10-session e1RM bar on an 80→100 band.

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Bar, not line**, for both charts — avoids the theme-dependent blank-line
  Mermaid bug and false continuity across irregular sessions.
- **ISO-native labels** (W## / mm-dd) — every other date in the vault is ISO;
  dd/mm would be a novel, ambiguous, year-colliding format.
- **Contiguous zero-filled weekly window** — a lapse should show as elapsed
  zero bars, not be hidden by compression.
- **e1RM = loaded sessions only** (`best_e1rm_kg > 0`); pure-bodyweight
  exercises get no chart (caption says so).
- **Monthly-review chart cut** for v1 (low value-to-clutter); the Dashboard's
  12-week bar is the better volume-trend home.
- **Default `e1rm_points = 10`** (legibility — Mermaid doesn't thin or rotate
  x-labels), `volume_weeks = 12`.

## Watch / gotchas

- Charts are **auto-generated** into Dashboard + exercise notes on every
  `vault`/`full` run; no command. Turn off with `[charts] enabled = false`.
- **Duplicate same-day e1RM label** (e.g. Incline Bench `01-24` ×2) is a known
  cosmetic nit — both bars are real loaded sessions; left as-is.
- If a chart ever renders **blank** in Obsidian, it's almost certainly the
  theme/CSS line-stroke issue — but both charts are bars specifically to dodge
  that, so it shouldn't happen. xychart-beta needs Obsidian on Mermaid ≥
  10.6.0 (current Obsidian is far past it).
- `HevyBrain Coach` still pending its first fire (was Sat 13/06; next slot
  Sun 14/06 19:00).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice7-progress-charts.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 yet (first ever run — `logs\
> coach.log` / `Get-ScheduledTaskInfo`)? Build the next slice — recommended:
> **C1 coach memory** (briefing includes last recommendations + a computed
> "was it followed?") or **A2 year-in-review** note (totals, PRs, best month,
> streaks) or **F4** (swap some cache-side analytics to `GET
> /v1/exercise_history/{id}`). Offline tests with fixtures, ruff clean, one
> slice, commit per coherent step, push at end, update HANDOFF + dated handoff
> + carry-on. Locked: explicit-push fence; free tiers; read-only knowledge
> bridge (never write pipeline folders, never read sources/); repo private
> until key rotation. E4 (ingest programming episodes) stays an atlas-pipeline
> task. Do not re-litigate.
