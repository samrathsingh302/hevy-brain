# hevy-brain — Overnight Autonomous Build Plan (15/06/2026) — v2 (red-teamed)

**Author:** orchestrator session (Opus 4.8, max effort), 15/06/2026 ~03:40 UTC.
**v2:** revised after an adversarial red-team (planner agent) found 4 CRITICAL + 4 MAJOR
defects vs the real source. All folded in; see §9 for the audit trail.
**Mode:** autonomous — Samrath asleep, full authority, **no questions**; all calls via
SAMRATH.md §3 defaults; every SAMRATH.md §4 trigger is **out of scope** (not touched).

**Baseline (verified):** `main` @ `1b6aa17`, clean + pushed. **338 tests pass** (Python
3.14), ruff + mypy clean (41 files). Coach 19:00 debut fired clean (wrote `2026-06-14
Briefing.md`). Sync healthy (285 workouts, idempotent). Codex debt `--commit 1090c3c`
cleared (cosmetic-only). **Account is in a ~65-day lapse** (last session 2026-04-11) —
every feature MUST degrade gracefully with no recent training.

---

## 0. Operating contract

- **Topology:** ONE orchestrator + a **fresh Opus 4.8 builder per slice**, **serial**.
  Serial makes write-sets trivially disjoint (no parallel writers → C1/C3 cannot occur on
  the hot files `cli.py`/`config.py`/`dashboards.py`/`build.py`). No worktrees (single
  writer — ORCHESTRATION §13).
- **Builder commits, orchestrator verifies + pushes.** Builder runs pytest+ruff+mypy green,
  commits (house format), returns SHA + structured summary, does **NOT push**. Orchestrator
  runs the two-pass verify on the SHA, pushes iff accepted (§3). One writer to origin.
- **Single-writer docs:** HANDOFF / CHANGELOG / README / dated handoff = orchestrator only,
  at close. Builders touch ONLY their slice write-set (kills C10).

## 1. Orchestrator decomposition (ORCHESTRATION §8)

> **PIPELINE:** S1→S2→S3→S4→S5→S6, each gated by a passing two-pass verify before the next
> starts (M7 pinned-ref). **PARALLEL/ISOLATION:** none (serial single writer).
> **SYNTHESIS:** orchestrator — verifies, holds §4 gates, writes shared docs, pushes.
> **QUESTION BATCH:** empty. **§4 GATES held, never crossed:** key rotation, public flip,
> D1 history rewrite, slice-12 live-proof, `_shared-context` reconcile, ANY Hevy write.

## 2. GLOBAL FENCES — apply to EVERY slice (a violation = failed slice, even if the code works)

1. **Vault writes only via `VaultWriter`**, only under `Hevy/` (path-jail). Atomic only.
2. **Preserve user content below `%% hevy-brain:end %%`** (`MANAGED_MARKER`, `writer.py:21`).
   Never emit it yourself; the writer handles it.
3. **Idempotency is sacred:** a second `vault` build with the same `today` = **0 diffs**.
   NO new per-build/volatile content in managed notes (no `datetime.now()`, no random
   order, no unseeded set ordering). Every note slice ships an idempotency test.
4. **Never delete a workout note** (archive, never destroy). N/A here.
5. **Offline tests only** — never touch the real account; use `conftest.py` factories
   (`make_workout`/`make_exercise`/`make_set`, `conftest.py:10/15/31`) or inline fixtures.
6. **No writes to Hevy.** None of these slices push. Don't add a write path.
7. **Honesty discipline (HARD for S5/S6):** any training-science statement is labelled
   **general-knowledge** (NOT a cited claim — the corpus has none, surfaced honestly
   elsewhere). Objective arithmetic on the user's own lifts (S1/S4) is "based on your data",
   not advice. Never invent a programming/nutrition claim or imply medical advice.
8. **No body data on anything published.** These slices don't publish; keep bodyweight off
   any non–Body-Log surface.
9. **Typed + clean:** `from __future__ import annotations`, full hints, ruff clean, mypy
   clean (bare `python -m mypy`, configured `files=['hevy_brain']`).
10. **British English, dd/mm/yyyy, £, free tiers. Stdlib over new deps** (none needed here).
11. **One concern per slice. Stay in your write-set.** Spot a bug/cleanup outside it →
    **report in your return, do NOT fix it** (M1). Defer ideas to the handoff.
12. **Lapse-safe:** ~65 days of no training on the real account. Every feature does
    something sensible (clear "not enough recent data" / honest-empty), never crashes or
    emits nonsense, when there's no recent training. **Bodyweight sets carry `weight_kg=None`
    (371 of them in the cache); half-open rep ranges `{start:8,end:null}` exist** — handle both.
13. **Repo reality wins.** If this spec disagrees with the code, the code is truth — follow
    it and note the discrepancy in your return.
14. **APPEND-ONLY signature params (load-bearing).** When you add a parameter to
    `render_dashboard`, `render_exercise_note`, `generate_exercise_notes`, or any function
    with positional callers, **append it at the END of the signature with a safe default —
    NEVER insert before an existing param.** Positional callers exist (e.g.
    `tests/test_vault_build.py:131` calls `render_dashboard([], {}, {}, {}, TODAY,
    volume_weeks=12)`); inserting silently mis-binds them.
15. **`tests/test_vault_build.py` is load-bearing for every note slice (S1/S2/S5/S6)** — it
    runs full `build_vault` twice and asserts 2nd pass = 0 changes (idempotency net,
    `:170-177`) and has positional `render_dashboard` callers (`:131`). **Re-run it and
    EXTEND it** for your section; it is NOT "edit only if needed".

## 3. Per-slice verification protocol (the house two-pass + push)

After the builder returns its SHA, the orchestrator runs:

1. **PRIMARY — Codex (different model, read-only):** `codex review --commit <SHA>`. Never
   `--fix`/apply. Unavailable (rate limit) → log debt with the re-run command, proceed
   (verifier + tests carry it; debt recorded).
2. **SECONDARY — fresh Opus 4.8 `verifier` subagent:** re-read the diff against *this spec
   section* — edge cases (empty/null/huge/unicode/dates), idempotency, fence violations,
   lapse-safety, likely bugs by simulating inputs (not restating the diff). SHIP/FIX +
   `file:line` evidence.
3. **Reconcile by the evidence rule** (`file:line`/repro beats assertion; never average):
   - Both clean → **accept**: push, append outcome to the live dated handoff, advance.
   - Real issue → **forward-fix**: spawn a builder scoped to the same slice; the fix
     completes and **re-passes the two-pass BEFORE the next slice starts** (never deferred
     past it — a later slice may also touch the shared file). Prefer forward-fix to revert.
   - Unsalvageable → reset the single **un-pushed** local commit (reflog-recoverable; this
     session's own commit, not §4-destructive), log, **skip** to the next slice.
4. **Runtime smoke** where cheap: `python -m hevy_brain.cli --help` (exit 0) after CLI
   slices; for note slices a scratch `vault` rebuild + a 2nd build = 0 changes.

## 4. Stop conditions

- Slice fails two-pass + not cheaply forward-fixable → skip, log, continue.
- **Orchestrator self-degradation** (canary "hey daddy" slips, contradictions, re-reading,
  thinning) → **STOP**, write dated handoff + carry-on, push what's accepted, recommend a
  fresh session (PROMPTING_GUIDE §9). Don't soldier on degrading.
- Backlog drained → closeout.

## 5. The slice backlog (best-first; objective/low-risk before opinionated)

| # | Slice | Value | Surface | Honesty class |
|---|-------|-------|---------|---------------|
| S1 | Per-lift progression targets (B1) | HIGH (the one genuinely-missing feature) | Exercise notes | objective (own data) |
| S2 | Consistency heatmap | HIGH (CV optics) | Dashboard | objective |
| S3 | `export --csv` | MED-HIGH | new CLI cmd | objective |
| S4 | `diff` last-vs-prior session | MED | new CLI cmd | objective |
| S5 | Deload-readiness flag | MED | Dashboard | **general-knowledge** |
| S6 | Volume-landmark / MEV check | MED | Dashboard | **general-knowledge** |

## 6. Session prompt library — per-slice builder prompts

Orchestrator prefixes every builder spawn with:
> You are a fresh Opus 4.8 **builder** for hevy-brain. READ FIRST, in order: `CLAUDE.md`,
> `HANDOFF.md`, then this slice spec. The codebase facts here are pre-verified against the
> real source — trust them but CONFIRM exact shapes by reading the cited file before coding
> (fence §2.13). Obey ALL of `docs/OVERNIGHT-PLAN-2026-06-15.md` §2 GLOBAL FENCES (esp. §2.3
> idempotency, §2.12 lapse-safety, §2.14 append-only params, §2.15 re-run+extend
> `test_vault_build.py`) and §3. Verify green locally (`python -m pytest tests -q`,
> `python -m ruff check hevy_brain tests`, `python -m mypy`) BEFORE committing. ONE coherent
> commit, house format (footer `Co-Authored-By: Claude Opus 4.8 (1M context)
> <noreply@anthropic.com>`). **Do NOT push. Do NOT touch HANDOFF/CHANGELOG/README or any
> file outside your write-set.** Self-critique once before returning. RETURN (≤25 lines):
> commit SHA · files changed · test count before→after · key decisions (+ the §3-default
> used) · any out-of-write-set issue spotted (report, didn't fix) · self-critique result ·
> how you proved idempotency + lapse-safety.

### S1 — Per-lift progression targets (B1)

**Goal:** add a deterministic, **evergreen** "next session target" to each exercise note —
"next time you do this lift, try X kg × Y reps" — derived purely from the user's own best
recent set. Objective arithmetic, not training-science advice.

**DECISION (locked, was CRITICAL-3): targets are TIMELESS, not recency-gated.** An exercise
note is evergreen; "next time you do this lift" is sensible even mid-lapse and claims nothing
about recent training. So S1 does **not** need `today` and does **not** gate on recency. (The
lapse is surfaced honestly by the Dashboard lapse callout + S2 heatmap, not here.)

**Write-set (exclusive):** `hevy_brain/analytics/progression.py` (new) ·
`hevy_brain/vault/exercises.py` (edit — **MANDATORY**: add an appended param to BOTH
`render_exercise_note` and `generate_exercise_notes`, and insert one managed section) ·
`hevy_brain/config.py` (edit — add `[progression]` block, two sites) ·
`hevy_brain/vault/build.py` (edit — **MANDATORY**: pass the progression config at the
`generate_exercise_notes` call site, ~`build.py:37-39`) · `tests/test_progression.py` (new) ·
`tests/test_vault_build.py` (re-run + extend per §2.15).

**Codebase facts (CONFIRM by reading; corrected in v2):**
- `epley_1rm(weight_kg, reps)->float` (`prs.py:8`).
- `exercise_histories(records)->dict[title→history]` (`prs.py:38`). Each `history` has
  `sessions` (list), `best_weight_kg`, `best_e1rm_kg`, `template_id`, `last_performed`,
  `times_performed`.
- **`sessions[]` entries have NO per-session set list.** Each entry (`_session_entry`,
  `prs.py:25-35`) is `{date, workout_id, workout_title, top_weight_kg, best_e1rm_kg,
  best_set, volume_kg, sets(count), reps(session total)}` where **`best_set` is the full set
  dict of the highest-e1RM set** (`{weight_kg, reps, type, rpe, ...}`). **Sort `sessions` by
  `date` and take the most recent; don't assume order.**
- `render_exercise_note(history, workout_paths, e1rm_max_points=0)` (`exercises.py:19`) and
  `generate_exercise_notes(writer, histories, workout_paths, e1rm_max_points)`
  (`exercises.py:85`) take **no** config arg — you MUST add one (appended, fence §2.14).
- Config two-site pattern: a field on `Config` (`config.py:18`) AND a parse site in
  `load_config` (`config.py:71`, block-dict pattern `:81-87`).

**Locked heuristic (double progression — operate on the most recent session's `best_set`):**
- Config `[progression]`: `enabled=true`, `rep_low=8`, `rep_high=12`, `increment_kg=2.5`,
  `min_sessions=3`.
- Basis `(w, r)` = the most-recent session's `best_set` → `(best_set["weight_kg"],
  best_set["reps"])`. **Skip (return None, no section) if:** `enabled` is false, OR
  `best_set["weight_kg"]` is `None` or `<= 0` (bodyweight-only — no load to progress), OR
  `best_set["reps"]` is None/0, OR `times_performed < min_sessions`.
- `if r < rep_high`: target `(w, r+1)` — "add a rep".
  `else`: target `(round(w + increment_kg, 1), rep_low)` — "add load, reset reps".
- **No-regression guard:** if `epley_1rm(target) <= epley_1rm(w, r)`, fall back to `(w, r+1)`.
- Return `{"exercise", "current_weight_kg", "current_reps", "target_weight_kg",
  "target_reps", "note"}` or `None`.

**Render:** one managed section, deterministic placement (e.g. a `> [!tip] Next session
target` callout) — "Based on your best set last time (W kg × R), aim for **Wt kg × Rt**."
No timestamp, no `today`.

**Done criteria:** tests cover: normal lift (rep-add), top-of-range lift (load-add+reset),
bodyweight-only `best_set.weight_kg=None` (None), `times_performed<min_sessions` (None),
the no-regression guard, and **idempotency** (build twice → identical note). Suite green,
ruff+mypy clean; `vault` rebuild changes only exercise notes.

### S2 — Consistency heatmap

**Goal:** a GitHub-style training-consistency heatmap on the Dashboard over the last ~26
weeks; lapses read honestly as empty.

**Write-set (exclusive):** `hevy_brain/vault/heatmap.py` (new) ·
`hevy_brain/vault/dashboards.py` (edit — add `_consistency_heatmap_lines` helper + insert
its section; add an **appended** param to `render_dashboard`, fence §2.14) ·
`hevy_brain/config.py` (edit — extend `[charts]` with `heatmap_enabled=true`,
`heatmap_weeks=26`) · `hevy_brain/vault/build.py` (edit — pass the new params at the
`render_dashboard` call site) · `tests/test_heatmap.py` (new) · `tests/test_vault_build.py`
(re-run + extend per §2.15).

**Codebase facts (verbatim — CRITICAL-precise):**
`render_dashboard(records, histories, workout_paths, store_meta, today, templates=None,
overrides=None, volume_weeks=0, lapse_nudge_days=0, guide_lapse_days=14)`
(`dashboards.py:92`). **Append your param after `guide_lapse_days`.** Follow the helper
pattern (`_session_quality_lines` `:55`, `_lapse_callout` `:22`) and the `chart_section`
"no orphan heading" discipline (`charts.py:109`). Records carry `start_time` (datetime) and
`exercises[].sets[]` (each set `{type, weight_kg, reps, ...}`); warm-ups are `type=="warmup"`.

**Locked rendering (metric + cutoffs fixed in v2 — was MAJOR-S2):**
- **Metric = WORKING-SET COUNT per day** (count of non-warmup sets), NOT volume — bodyweight
  days have volume 0 (371 such sets) but are real training and must show a shade.
- A **fenced monospace block** (```` ```text ````), **7 day-rows (Mon→Sun) × `heatmap_weeks`
  columns**, contiguous calendar ending at the ISO week of `today`. Cell glyph by an
  **equal-width 5-band** scale over `[0, max_count]` where `max_count` = max daily
  working-set count in the window: band 0 (no sets) = ` `, then ` · ░ ▒ ▓` for the 4
  positive bands (` ▓` top). Include a one-line legend + the date range (derived from `today`,
  the only date label — no other timestamp).
- **Omit the whole section** (return `[]`, no orphan heading) if `heatmap_enabled` is false,
  OR `max_count == 0` (no training in window — guards division), OR <2 distinct trained weeks
  in the window.

**Done criteria:** tests cover: dense history → 7 rows + legend; sparse/lapsed → mostly-empty
cells, no crash; `max_count==0` → no section (div-by-zero guard); disabled → no section;
**idempotency** (twice → identical). Suite green, ruff+mypy clean; rebuild changes only the
Dashboard.

### S3 — `export --csv`

**Goal:** `hevy-brain export --csv [--out PATH] [--kind workouts|sets]` writes the cache to
CSV for external analysis. Stdlib only.

**Write-set (exclusive):** `hevy_brain/export.py` (new) · `hevy_brain/cli.py` (edit — `export`
top-level parser + `_cmd_export` + dispatch in `main`) · `.gitignore` (edit — add `exports/`
so exported personal training data is never git-tracked) · `tests/test_export.py` (new).

**Codebase facts:** CLI: `build_parser()` (`:814`) registers subparsers; `main()` (`:961`)
dispatches `if args.command == ...`; handlers `_cmd_*`; dispatch block `:971-991`. Use
`models.build_records(store.workouts)` for clean records (pattern at `cli.py:190`,
`build.py:28`). `Config.base_dir` = repo root (`Path.cwd().resolve()`, `config.py:75`) — a
safe export root, outside the vault.

**Locked behaviour:**
- `--kind workouts` (default): one row/workout — `date,title,duration_min,volume_kg,
  total_reps,exercise_count,hevy_id`.
- `--kind sets`: one row/working+warmup set — `date,workout_title,exercise,set_index,
  set_type,weight_kg,reps,rpe`.
- **`None` values serialise as an empty cell `""`, never the string "None"** (371 sets have
  `weight_kg=None`; RPE often None).
- `--out` is a file path; if omitted → `<base_dir>/exports/hevy-<kind>.csv` (create the dir).
  **Never write inside the vault.** `csv` module, `newline=""`, UTF-8. Deterministic order
  (chronological; then exercise order; then set index). Print written path + row count.
- Empty cache → header-only file + a clear message, **exit 0** (export of nothing isn't an
  error like `doctor`'s FAIL; state this divergence).

**Done criteria:** tests cover: workouts headers+rows; sets headers+rows; `None→""`; empty
cache (header-only, exit 0); default-path creation; `--out` honoured. Suite green, ruff+mypy
clean; `export --help` and a real `--csv --kind sets --out <tmp>` run clean.

### S4 — `diff` last-vs-prior session

**Goal:** `hevy-brain diff [exercise]` prints an objective comparison of the two most recent
sessions — overall (no arg) or for one exercise. CLI report, no vault write.

**Write-set (exclusive):** `hevy_brain/analytics/sessiondiff.py` (new) · `hevy_brain/cli.py`
(edit — `diff` parser + `_cmd_diff` + dispatch) · `tests/test_sessiondiff.py` (new).

**Codebase facts:** reuse `reconcile.resolve_exercise(histories, name)->(title|None,
candidates)` (`reconcile.py:40`; exact > unique substring; ambiguous → candidates).
`exercise_histories` sessions carry `best_set` (the top set) + `best_e1rm_kg` + `top_weight_kg`
+ `volume_kg` + `reps`. `models.build_records` gives chronological records (drops no-start_time
workouts, `models.py:82`); "most recent two" = `records[-1], records[-2]`.

**Locked behaviour:**
- No arg: two most recent workouts; print `volume_kg`, `duration_min`, `exercise_count`
  deltas, and for each **shared exercise** its top-set change. **The overall case has no
  pre-stored (weight×reps) top set** — scan `record["exercises"][i]["sets"]` (non-warmup) for
  the heaviest set to report `kg × reps` (was MINOR-S4).
- `exercise` arg: resolve the name; that exercise's two most recent `sessions`; print top-set
  (from `best_set`), est-1RM (`best_e1rm_kg` or Epley), reps, volume deltas with arrows ↑/↓/=.
- Honest degrade: <2 workouts (or <2 sessions for the exercise) → "need at least two sessions
  to diff", exit 0; ambiguous name → list candidates, exit 1; unknown name → exit 1.
- British formatting, no body data, stdout only.

**Done criteria:** tests cover: overall deltas; per-exercise deltas; single-session message;
ambiguous-name candidates; unknown-name. Suite green, ruff+mypy clean; `diff --help` clean.

### S5 — Deload-readiness flag (general-knowledge)

**Goal:** a Dashboard callout that fires ONLY on objective, deterministic thresholds when a
deload week may be worth considering — explicitly labelled a general training-science
heuristic, not personalised/medical advice. Correctly **silent on the current lapsed account.**

**Write-set (exclusive):** `hevy_brain/analytics/deload.py` (new) · `hevy_brain/vault/
dashboards.py` (edit — `_deload_callout` helper + insert; **appended** `render_dashboard`
param, §2.14) · `hevy_brain/config.py` (edit — `[analytics]` gains `deload_weeks=6`,
`deload_rpe=8.5`) · `hevy_brain/vault/build.py` (edit — thread params) · `tests/test_deload.py`
(new) · `tests/test_vault_build.py` (re-run + extend, §2.15).

**Codebase facts:** `detect_plateaus(histories, today, plateau_weeks)` (`patterns.py:128`) —
needs ≥`plateau_weeks` sessions in the recent window, so it is **silent during the lapse**
(accepted). `stats.weekly_series(records)` (`stats.py:88`) returns **only weeks that have
training** (no zero-weeks), and `stats.week_start(day)` gives a week's Monday. `session_quality.
rpe_coverage(records)` (`session_quality.py:50`) for RPE. Dashboard helper pattern as S2.

**Locked trigger (algorithm specified in v2 — was MAJOR-S5; ALL must hold):**
- **Consecutive-trained-weeks run:** from the last workout's ISO week (`week_start(last
  workout date)`), walk backward one week at a time over the set of trained weeks (build the
  trained-week set from `weekly_series`/`week_start`); count the run length until the first
  week with **zero** sessions. Require run length `>= deload_weeks`.
- **AND the run ends near now:** the last workout is within ~14 days of `today` (else lapsed
  → DO NOT fire — you can't be "ready to deload" from training you're not doing).
- **AND a fatigue signal:** `detect_plateaus(histories, today, plateau_weeks)` is non-empty
  (≥1 stalled lift) **OR** mean working-set RPE over the recent window `>= deload_rpe`.
- Callout (only when ALL hold): `> [!note] Deload readiness` + the objective evidence (N
  straight weeks; which lift stalled / the RPE figure) + a literal line: "This is a general
  training-science heuristic, not personalised or medical advice." Omit entirely otherwise.

**Done criteria:** tests cover: fires on synthetic continuous-weeks + plateau/high-RPE data
ending near `today`; silent on lapsed/real-shaped data; silent on short history; the
general-knowledge label present when it fires; **idempotency**. Suite green, ruff+mypy clean;
Dashboard-only change.

### S6 — Volume-landmark / MEV check (general-knowledge)

**Goal:** a Dashboard table comparing recent weekly working-sets-per-muscle-group against
**user-configurable** MEV/MAV/MRV bands — labelled a general guideline, bands owned by the
user in `config.toml`. Degrades honestly with no recent training.

**Write-set (exclusive):** `hevy_brain/analytics/landmarks.py` (new) · `hevy_brain/vault/
dashboards.py` (edit — `_landmarks_lines` helper + insert; **appended** `render_dashboard`
param, §2.14) · `hevy_brain/config.py` (edit — new `[landmarks]` block, per-group
MEV/MAV/MRV defaults from published general ranges, user-editable) · `hevy_brain/vault/
build.py` (edit — thread) · `tests/test_landmarks.py` (new) · `tests/test_vault_build.py`
(re-run + extend, §2.15).

**Codebase facts (corrected in v2 — was CRITICAL-4 + MAJOR-S6):**
- `redesign.weekly_sets_by_group(window, weeks, templates=None, overrides=None)->dict[group→
  float]` (`redesign.py:62`) returns **Σ working sets ÷ weeks** — it already divides. So you
  must pass a `window` and the **weeks actually covered**, not a blind constant.
- **Anchor the window at the LAST workout, not `today`** (mirror redesign's lapse anchor,
  `redesign.py:129-134`). Window = `records_in_range(records, last_workout_date -
  landmark_weeks*7d, last_workout_date + 1d)`; `effective_weeks` = number of distinct trained
  ISO weeks in that window (≥1). Call `weekly_sets_by_group(window, effective_weeks, ...)`.
- `muscle_group` (`patterns.py:79`) returns one of chest/back/shoulders/biceps/triceps/legs/
  core/**other**; `muscle_overrides` can introduce arbitrary group strings.
- `records_in_range(records, start, end)` exists in `stats.py` (or `patterns`/`comeback` —
  confirm) for windowing.

**Locked behaviour:**
- Config `[landmarks]`: `landmark_weeks=4` + per-group `{mev, mav, mrv}` defaults (sane
  published general ranges; user-editable). Classify each **present** group with a band:
  `below MEV` / `MEV–MAV (maintenance→growth)` / `MAV–MRV (productive)` / `above MRV (high)`.
- **Skip any present group that has NO configured band** (don't crash, don't invent), and
  **always exclude `other`** (was MAJOR-S6).
- **Empty window / lapsed** (no records in window, or last workout >~2 weeks before `today`)
  → render a single honest line "No recent training to assess against volume landmarks." (or
  omit the section) — NEVER classify every group `below MEV` on an empty window (was CRITICAL-4).
- Section prefixed with a clear "general guideline, not personalised advice — edit the bands
  in `config.toml`" line.

**Done criteria:** tests cover: classification across all four bands; a config override moving
a band; a present group with no band default → skipped (no crash); `other` excluded; the
lapse/empty-window honest degrade; the general-knowledge label present; **idempotency**.
Suite green, ruff+mypy clean; Dashboard-only change.

## 7. Deferred / excluded (decisions, with reasons)

- **`doctor` vault-drift check — DEFERRED deliberately.** The robust version (re-render each
  managed note, diff the managed region) false-positives on daily date-derived fields
  (`Dashboard.updated`, reviews, body log all change at the day boundary). A noisy check
  undermines `doctor` on a CV piece. Revisit supervised as a proper `vault --dry-run` with
  volatile fields excluded. (Judgement call per SAMRATH.md §3.)
- **§4 — held for Samrath, untouched:** key rotation → flip; D1 history rewrite; slice-12
  live-proof (needs a real pushed+trained draft); `_shared-context` reconcile; any Hevy
  write. E4 stays atlas-pipeline.
- **Optional cleanup:** the merged `overnight-audit-2026-06-14` branch + the untracked
  cross-repo `docs/VERIFY-AND-CLOSEOUT-2026-06-14.md` — left as-is (harmless; vault-level call).

## 8. Execution log (orchestrator appends live; mirror in docs/handoffs/2026-06-15-overnight-autonomous.md)

- 03:40 — plan v1 authored; baseline GREEN; pre-flight done; codex debt cleared; coach debut confirmed.
- 03:55 — red-team (planner) returned REVISE: 4 CRITICAL + 4 MAJOR; plan v2 folds all in (§9).
- (slices logged below as they complete)

## 9. Red-team round 1 — defects fixed (audit trail)

- **CRITICAL-1 (S1 input):** `sessions[]` has no per-session set list → heuristic now keys on
  the most-recent session's `best_set` (the stored top set), stated explicitly.
- **CRITICAL-2 (S1 threading):** editing `exercises.py` (both signatures, appended) +
  `build.py` call site is now MANDATORY in the write-set, not "if needed".
- **CRITICAL-3 (S1 lapse):** locked decision — targets are **evergreen/timeless**, no `today`,
  no recency gate; lapse surfaced elsewhere.
- **CRITICAL-4 (S6 window):** window now **anchored at the last workout** with **effective
  weeks** division; empty/lapsed window hits the honest-degrade branch, never "all below MEV".
- **MAJOR-S5:** consecutive-trained-weeks **algorithm specified** (walk back over trained-week
  set from last workout; run must end within ~14d of `today`).
- **MAJOR-S2:** heatmap metric = **working-set count** (not volume, for bodyweight days);
  **equal-width 5 bands**, `max_count==0` → omit (div-by-zero guard).
- **MAJOR-S6:** **skip groups with no band**, exclude `other`.
- **MAJOR (cross-slice):** §2.14 **append-only params** + §2.15 **`test_vault_build.py`
  load-bearing** added as global fences.
- **MINOR-S3:** `None→""` in CSV + `exports/` added to `.gitignore` (personal-data hygiene).
- **MINOR-S4:** overall diff scans `sets[]` for the top set (reps not stored beside max_weight).
- **MINOR-S2 precision:** verbatim `render_dashboard` signature quoted.
