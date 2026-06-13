---
status: done
agent: slice14-builder-1
goal: "Slice 14: A3 lapse-detection nudge — a quiet-streak callout on the Dashboard that escalates into a guide-return prompt"
outcome: "comeback.lapse_nudge + a Dashboard [!warning] callout: a gentle nudge from nudge_days (default 7), escalating to a `guide return` pointer once the gap reaches guide.lapse_days (14). New [analytics] lapse_nudge_days config. 318 offline tests (was 313), ruff clean. Live rebuild touched only the Dashboard (idempotent) — the real 63-day lapse renders the callout."
gotchas: "Two thresholds, deliberately tied: lapse_nudge_days (when to START nudging, [analytics], default 7) and guide_lapse_days (when it becomes a 'lapse' worth a comeback plan, [guide], default 14 — reused, not duplicated). render_dashboard gained lapse_nudge_days (default 0 = OFF) + guide_lapse_days (default 14); the 0 default keeps the existing test (render_dashboard([], {}, {}, {}, TODAY, volume_weeks=12)) and any other caller callout-free unless build.py passes the real value. The callout sits at the TOP of the Dashboard (after the athlete line, before Totals) so it's the first thing seen. lapse_nudge returns None when disabled / no history / below threshold — never crashes an empty cache."
carry-on: "A6 Dataview/Bases starter pack (Hevy/Queries.md) is the last unbuilt A-item; otherwise prove slice 12's adherence capture live (push a guide draft, train it, run coach). E4 ingestion stays an atlas-pipeline task."
---

# 13/06/2026 — Slice 14: A3 lapse-detection nudge

Quick, high-value A-item: the Dashboard should *say something* when you go
quiet, not just sit there. Reuses the lapse analytics already built for
`guide return`.

## Done (commit ea459e8, pushed)

1. **`analytics/comeback.py`** — `lapse_nudge(records, today, *, nudge_days,
   lapse_days)`: returns the `lapse_status` facts + a `severity` (`nudge` →
   `lapse` once the gap reaches `lapse_days`), or None below `nudge_days` / no
   history / disabled (`nudge_days <= 0`).
2. **`vault/dashboards.py`** — `_lapse_callout` renders a `[!warning]` block at
   the Dashboard top: a gentle "time to get back in?" nudge, or at lapse
   severity a pointer to `hevy-brain guide return`. `render_dashboard` gained
   `lapse_nudge_days` (default 0 = off) + `guide_lapse_days` (default 14).
3. **`config.py` / `config.example.toml`** — `[analytics] lapse_nudge_days`
   (default 7), documented.
4. **`vault/build.py`** — passes `config.lapse_nudge_days` +
   `config.guide_lapse_days`.
5. **Tests** — `test_comeback.py` (lapse_nudge: silent-below / nudge / escalate-
   at-threshold / disabled+empty) and `test_vault_build.py`
   (`test_dashboard_lapse_callout`: no callout when recent, lapse callout +
   guide-return pointer at 20 days).

## Process

No design panel (small, clear extension). Decision worth noting: rather than a
new "big lapse" constant, the nudge **escalates at `guide.lapse_days`** — the
same point `guide return` treats a gap as a lapse — so the two features agree on
when a comeback plan is the right call. Default-off `render_dashboard` params
kept the change zero-impact on existing callers.

## Verify

`python -m pytest tests -q` → **318 passed** (was 313) · `python -m ruff check
hevy_brain tests` → clean. **Live:** `hevy-brain vault` re-rendered **only** the
Dashboard (0 other notes). The callout reads: "**63 days** since your last
session (2026-04-11, _forgot to track lol (first day back after hol)_). That's a
lapse — run `hevy-brain guide return` for a scaled comeback plan."

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Nudge from 7 quiet days** (`[analytics] lapse_nudge_days`, default 7) — a
  week off is worth flagging for a 4–5×/week trainer.
- **Escalate to a guide-return prompt at `guide.lapse_days` (14)** — one shared
  notion of "lapse", not a second threshold.
- **Dashboard only** (top, before Totals) — most visible; weekly review left
  alone to keep the slice S-sized.
- **render_dashboard params default to no-op** — existing callers unaffected.

## Watch / gotchas

- Two thresholds (nudge vs lapse) — don't conflate; the nudge starts earlier.
- `render_dashboard`'s `lapse_nudge_days` defaults to 0 (off); only build.py
  turns it on with the config value.
- `HevyBrain Coach` still pending first fire (next Sun 14/06 19:00 — tomorrow).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice14-lapse-nudge.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — `logs\coach.log`
> / `Get-ScheduledTaskInfo`)? Build the next slice — **A6 Dataview/Bases starter
> pack** (`Hevy/Queries.md`: ready-made queries over the note frontmatter —
> recent workouts, PRs, volume by week, etc.) is the last unbuilt A-item.
> Otherwise close slice 12's live gap: push a guide draft (`push routine`),
> train it, then `coach`, to prove the adherence capture path end to end.
> Offline tests with fixtures, ruff clean, one slice, commit per coherent step,
> push at end, update HANDOFF + dated handoff + carry-on. Locked: explicit-push
> fence; vault rebuildable **offline** (only `verify` makes a read-only network
> call); free tiers; read-only knowledge bridge (never write pipeline folders,
> never read sources/); bodyweight/body data stays off anything published; repo
> private until key rotation. E4 stays an atlas-pipeline task. Do not
> re-litigate.
