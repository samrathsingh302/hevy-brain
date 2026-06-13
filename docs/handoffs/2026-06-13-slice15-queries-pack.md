---
status: done
agent: slice15-builder-1
goal: "Slice 15: A6 Dataview/Bases starter pack — a Hevy/Queries.md of ready-made queries over the note frontmatter"
outcome: "New vault/queries.py renders a managed, static Hevy/Queries.md with Dataview queries over #hevy/workout / #hevy/exercise / #hevy/review/* (recent workouts, biggest sessions, this month, strongest lifts, most-trained, going-stale, review logs) + a Bases pointer. 322 offline tests (was 318), ruff clean. Live: written once, second build 0 changes (idempotent). Completes section A (Insights)."
gotchas: "The note is intentionally STATIC — no per-build timestamp in frontmatter (unlike Dashboard/Body Log which stamp `updated: today`), so it writes once and never churns; only editing the query set in queries.py re-renders it. The queries run LIVE via the Dataview plugin, so they don't need hevy-brain to refresh. Two TABLE lines hit ruff E501 (>88) — shortened the column aliases (e.g. \"Est 1RM\"/\"Top\"), queries still valid. A test guards that every workout/exercise field the queries reference is real frontmatter (render a real note, parse YAML, assert the field set is present) — so a future frontmatter rename that breaks a query fails CI. User additions below the %% hevy-brain:end %% marker are preserved by VaultWriter.write like every managed note."
carry-on: "Section A is done. Open threads: prove slice 12's adherence capture live (push a guide draft, train, coach); the pre-public checklist (rotate HEVY_API_KEY → flip repo visibility). Otherwise C-series coach/guide depth. E4 ingestion stays an atlas-pipeline task."
---

# 13/06/2026 — Slice 15: A6 Dataview/Bases starter pack

The last A-item. Turns the frontmatter every note already carries into a
ready-to-use query surface, so the vault is explorable without writing DQL from
scratch — and completes **section A (Insights)** of the roadmap.

## Done (commit b1c3c17, pushed)

1. **`vault/queries.py`** (new) — `render_queries()` returns a managed
   `Queries.md`: a static body of `dataview` blocks over the real tags/fields:
   - Recent workouts · Biggest sessions by volume · This month's training
     (`#hevy/workout`: `date`, `volume_kg`, `duration_min`, `total_reps`,
     `exercise_count`, `title`).
   - Strongest lifts (est-1RM) · Most-trained · Lifts going stale
     (`#hevy/exercise`: `best_e1rm_kg`, `best_weight_kg`, `times_performed`,
     `last_performed`, `total_volume_kg`).
   - Weekly / monthly review logs (`#hevy/review/{weekly,monthly}`:
     `sessions`, `volume_kg`, `start`, `month`).
   - A short **Bases** pointer (filter `tags contains "hevy/workout"`).
2. **`vault/build.py`** — wired in as the `queries` category
   (`writer.write("Queries.md", queries.render_queries())`).
3. **Tests** — `tests/test_queries.py` (4): static/idempotent; real tags +
   ≥6 dataview blocks present; **and a schema-drift guard** — render a real
   workout note and a real exercise note, parse their frontmatter, and assert
   every field the queries use is actually there.

## Process

No design panel (a content note). Key calls: **static note** (no `updated`
stamp) so it never churns; **live queries** (Dataview re-runs them, hevy-brain
doesn't); and the **drift-guard test** so the queries can't silently rot if a
note's frontmatter is renamed. Fixed two E501s by shortening column aliases.

## Verify

`python -m pytest tests -q` → **322 passed** (was 318) · `python -m ruff check
hevy_brain tests` → clean. **Live:** `hevy-brain vault` wrote `Queries.md` and
re-rendered nothing else; a **second** build reported **0 changes** — fully
idempotent, the static note included.

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Static note, no timestamp** — content is data-independent; daily churn would
  be noise.
- **Dataview-first, Bases as a pointer** — Dataview is the zero-setup common
  case; a full `.base` file risks shipping a format that drifts, so a short
  pointer instead.
- **Queries only reference fields that exist** — enforced by a test, not trust.
- **LIMIT 10–20** on the big lists — readable defaults; the user tunes below the
  marker.

## Watch / gotchas

- Editing the query set in `queries.py` re-renders the note (expected); nothing
  else triggers it.
- The drift-guard test is the early warning if a note's frontmatter schema
  changes — keep it green, or update both the note builder and the queries.
- `HevyBrain Coach` still pending first fire (next Sun 14/06 19:00 — tomorrow).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice15-queries-pack.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (first ever run — `logs\coach.log`
> / `Get-ScheduledTaskInfo`)? **Section A (Insights) is complete.** Pick from:
> (a) **prove slice 12's adherence capture live** — push a guide draft
> (`push routine`), train it, then `coach`, to exercise the capture→grade path
> end to end; (b) **the pre-public checklist** — rotate `HEVY_API_KEY`, update
> the User-scope env var, then `gh repo edit --visibility public`; (c) C-series
> coach/guide depth. Offline tests with fixtures, ruff clean, one slice, commit
> per coherent step, push at end, update HANDOFF + dated handoff + carry-on.
> Locked: explicit-push fence; vault rebuildable **offline** (only `verify`
> makes a read-only network call); free tiers; read-only knowledge bridge
> (never write pipeline folders, never read sources/); bodyweight/body data
> stays off anything published; repo private until key rotation. E4 stays an
> atlas-pipeline task. Do not re-litigate.
