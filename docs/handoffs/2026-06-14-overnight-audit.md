---
status: done
agent: overnight-audit-2026-06-14
goal: "Overnight autonomous correctness sweep of today's work (slice-17 pre-public hardening + the surfaces it certifies), per OVERNIGHT_AUDIT_PROMPT.md — fix what's safe, leave the repo green, one report."
outcome: "0 P0. Audited the slice-17 diff line-by-line + the safety/money fences it certifies, via 5 fresh-context auditors + a fresh verifier + my own reads. Repo ends GREEN: 333->336 offline tests, ruff + mypy clean, runtime smoke (doctor/status) healthy. 4 fix commits on branch overnight-audit-2026-06-14 (NOT pushed, NOT merged): removed HA fork-leftover scripts (P1 rot), README+PROMPT doc drift (P2), pre-commit ruff-hook nit (P3), and 3 money/config regression tests. The one genuine money nuance (coach --api budget is a best-effort SOFT cap, not a hard cap) is bounded + inherent + needs Samrath's call — PARKED, not touched. Data-loss fences + secrets/history all NIL (verified clean)."
branch: overnight-audit-2026-06-14
pre_audit_commit: f28a6d06811bb03148515364bd1e11ad2960b1b9
---

# Overnight audit — hevy-brain — 14/06/2026

> Autonomous, unattended, harsh. Companion run to `CODEBASE_AUDIT_PROMPT.md`,
> scoped to *today's work*. Nothing pushed; `_shared-context` left untouched.

## TL;DR (60-second read)

- **Audit window:** today (since 00:00 14/06) was one trivial prompt-doc commit
  (`f28a6d0`), so per the protocol's widening rule I scoped to **the last
  substantive session the newest handoff documents — slice 17 "pre-public
  hardening" (`606791b`→`f28a6d0`)**, audited line-by-line, **plus** the
  subsystems it touches / its correctness depends on: the **coach `--api`
  billing/budget path** (its headline fix; money), the `config` subfolder
  default + the `cache.set_measurements`/`_coach_recap` mypy changes, and the
  **doc-honesty claims** it made (the repo is CV-bound, key-rotation-gated for a
  public flip). The full 48h sprint (slices 1–17, ~60 commits) is the *whole
  tool* — that's the full-repo audit's job, deliberately out of scope here.
- **Pre-audit commit:** `f28a6d0` · **Branch:** `overnight-audit-2026-06-14`
  (4 fix commits on top; **not pushed, not merged to main**).
- **Health:** build (import/dispatch) ✅ · tests **333/333 → 336/336** (+3
  regression tests) · ruff ✅ · mypy ✅ (41 files) · runtime smoke ✅
  (`doctor` exit 0 — real env healthy, **285 workouts, synced 0.7h ago, hourly
  task alive**; `status` exit 0).
- **Found:** P0 **0** · P1 **2** · P2 **~5** · P3 **~8**.
  **Fixed:** 4 (HA fork scripts, README+PROMPT drift, pre-commit nit, 3 tests).
  **Reverted:** 0 (nothing derailed). **Left for you (morning):** the money
  soft-cap decision + ~9 parked items below.
- **Verdict:** **GREEN + safe to merge the branch.** Every change is
  doc/rot/test-hardening only — **zero `hevy_brain` runtime source touched** —
  and independently verified — **Codex** (primary): "no introduced correctness
  issues"; fresh **Opus verifier**: all 4 CORRECT, mutation-proven; full suite
  green; runtime smoke green. The only real correctness nuance (the
  `coach --api` budget is a *soft* cap) is **bounded, inherent, and parked** for
  your money-semantics call — it is **not** broken.

## Findings (every defect, deduped + severity-reconciled by me)

Severity reconciled by evidence, not by averaging the agents; I down-ranked one
over-claim (see A1 note) and dropped style-only nits.

| # | Sev | Finding | Evidence (file:line) | Status |
|---|-----|---------|----------------------|--------|
| C1 | **P1** | Home-Assistant fork-leftover scripts ship and contradict the "HA retired / fork purged" docs a recruiter reads. | `scripts/setup` (ran `pip install -r requirements.txt` — deleted file — + `echo "Run scripts/develop to start Home Assistant"` + a nonexistent `scripts/hacs_validate`); `scripts/develop` (`hass --config … --debug`). Contradicts `CHANGELOG.md:115`, `HANDOFF.md:323`. | **FIXED** `86df943` (deleted; no refs anywhere — verified) |
| A1 | **P1** (bounded) | The `coach --api` daily budget is a **best-effort soft cap, not a hard cap**: the billed Anthropic call (`advisor.py:259`) precedes the durable count (`cli.py:335-336`), so a crash/IO-fail in the bill→save window — or a failure of that save itself — loses the count and re-permits up to `max_per_day` calls next run. | `cli.py:331` generate_report (bills) → `:335` record_call → `:336` store.save(); `advisor.py:221-237`. | **PARKED** (see "Not fixed") — inherent client-side limit; needs your money-semantics call |
| C2 | P2 | `PROMPT.md` (historical spec, browsable when public) still showed `VAULT_SUBFOLDER=Fitness/Hevy`; every other site is `Hevy`. | `PROMPT.md:16,70` vs `config.py:23,105`, `README.md:112`, `CLAUDE.md`, `config.example.toml`. | **FIXED** `55cda72` (build-note added) |
| C3 | P2 | README "Use" block omitted 3 shipped commands (`doctor`, `verify exercise`, `guide redesign`) — undersells the tool. | `README.md:117-132` vs `cli.py:830,834,867`. | **FIXED** `55cda72` |
| E1 | P2 | The money path was under-tested: no test pinned the slice-17 billing ordering or the budget-guard *wiring* into `_cmd_coach`; the config-default test covered only the `load_config` fallback, not the dataclass field. | `tests/test_coach.py` (happy-path only); `tests/test_config.py:34`. | **FIXED** `2ba88a3` (3 regression tests; deeper billing-atomicity tests await the A1 decision) |
| A2 | P2 | An `OSError` from the coach save (`cli.py:336` / `_save_focus` `:302`) escapes the `except advisor.CoachError` handler (`:338`) → the metered command crashes with a raw traceback instead of a graceful "Coach failed". Same on the free path (`:314`, unguarded). No data loss (writes are atomic). | `cli.py:329-340`, `:314`. | **PARKED** (low value; see below) |
| A3 | P2 | Billed-but-not-counted: a 200 response with no usable `parsed_output` raises before `record_call` runs, so the user is charged but the call isn't counted. | `advisor.py:278-281` then `cli.py:335`. | **PARKED** (very narrow; same class as A1) |
| F4 | P3 | `.pre-commit-config.yaml` ruff hook had a stray `args: ["check"]` → `ruff check check` → `E902 cannot find file 'check'`; `pre-commit run ruff` would fail. | `.pre-commit-config.yaml:9` (was). | **FIXED** `8e7fd62` (verified `ruff check check`→E902) |
| A4 | P3 | `check_budget` is not hand-edit-tolerant (a corrupt `coach_calls` → AttributeError/TypeError) although its sibling meta consumers explicitly are. | `advisor.py:224`. | **PARKED** (respects slice-17's stated "skip defensive nits" decision) |
| D1 | P3 | `config.toml` was tracked in 4 historical commits; public history will expose `C:\Users\samra\…` (username) + an old vault path. **No API key was ever in it.** | `git log --all -- config.toml` → `50205bd 19189b8 c548319 59b9199`. | **PARKED** (needs history rewrite — pre-flip, your call; already in checklist) |
| D2 | P3 | Runtime deps floor-only, no lockfile (dev tools ARE pinned). | `pyproject.toml:14-19`. | **PARKED** (acceptable for a CLI; ADDITION) |
| D3 | P3 | CI actions tag-pinned, not SHA-pinned (first-party `actions/*` only). | `.github/workflows/{test,lint}.yml`. | **PARKED** (optional hardening) |
| N1 | P3 | Python **3.14** (the actual local interpreter, tests pass) is untested in CI (matrix is 3.12+3.13); no doc states an upper bound. | local 3.14.5 vs `test.yml:18`. | **NOTE** (optional: add 3.14 or state "tested 3.12–3.13") |
| N2 | P3 | `.mcp.json` (localhost Obsidian-MCP pointer, env-ref only, no secret) ships in the public repo. | `.mcp.json:7`. | **PARKED** (gitignore candidate; ADDITION) |

## Fixes made (one row per commit — all on the branch, none pushed)

| Commit | What | Why | Verified |
|--------|------|-----|----------|
| `86df943` | Delete `scripts/setup` + `scripts/develop` | HA fork cruft; broken (deleted `requirements.txt`, nonexistent `hacs_validate`); contradicts the docs (C1, P1) | grep: zero remaining refs (CI/README/CONTRIBUTING/pyproject); 336 tests green |
| `55cda72` | README: +`doctor`/`verify exercise`/`guide redesign`; PROMPT.md subfolder build-note | doc drift on a CV-bound repo (C3 P2, C2 P2) | commands confirmed real (`cli.py` subparsers + `--help`); default `Hevy` confirmed across all sites |
| `8e7fd62` | Drop `args: ["check"]` from the pre-commit ruff hook | the hook already runs `ruff check`; the extra arg broke it (F4 P3) | reproduced `ruff check check`→E902; YAML re-checked (sibling `ruff-format` untouched) |
| `2ba88a3` | +3 regression tests (no `hevy_brain` source changed) | money/config hot-spots were under-tested (E1) | 333→336 passed; verifier proved non-tautological by source mutation in a throwaway worktree |

Test count: **333 → 336**. ruff + mypy: clean throughout (mypy unaffected — it scans `hevy_brain` only, which I did not touch).

## Reverted / NOT fixed — your morning decision list (each with a recommendation)

1. **A1 — `coach --api` budget is a SOFT cap (P1, bounded). [money — your call]**
   The guard cannot be a hard cap: Anthropic bills server-side the instant
   `messages.parse()` returns, which is *before* any local write. Slice-17's fix
   and its comment (`cli.py:332-334`) are **accurate** — they correctly scope
   the guarantee to a *focus-snapshot* save failure (the count is saved first at
   `:336`). The residual windows (a crash between bill and `:336`, or `:336`
   itself failing) are inherent, not a regression. **Blast radius is tiny:**
   single-user personal CLI, sub-second crash window, at most `max_per_day`
   (default 4) extra Opus calls on an affected day.
   *Recommendation:* either (a) **accept** it and add a one-line code comment
   that the guard is a best-effort soft cap, or (b) **harden** by writing a
   provisional "call attempted" stamp immediately *before* `generate_report` and
   reconciling on success. (b) changes billing-count semantics → your taste call.
   The regression test added this session (`records_billed_call_before_focus_snapshot`)
   already pins the part the fix *does* guarantee.
2. **A2 — graceful save failure (P2).** Widen `cli.py:338` to
   `except (advisor.CoachError, OSError)` (and mirror on the free path at `:314`)
   so a disk-full on the unattended Sunday coach run logs "Coach failed" instead
   of a traceback. One line + a test. I left it to avoid touching the money file
   on an unattended run; no data loss today (writes are atomic).
3. **A3 — billed-but-not-counted on empty output (P2).** Same class as A1;
   fixing means recording the call right after `parse()` succeeds (inside
   `advisor.generate_report`), which also closes A1's window. Bundle with A1's
   decision.
4. **A4 — `check_budget` hand-edit tolerance (P3).** A `str(c)`/`isinstance`
   filter would match the hand-edit-tolerant siblings. Slice 17 explicitly chose
   to skip this class of defensive nit — I respected that; flag only.
5. **D1 — `config.toml` in git history (P3).** Username + old path, **no key**.
   Only resolvable by history rewrite, which is a pre-flip + irreversible action
   = your call. Already item 2 of the HANDOFF "Pre-public checklist".
6. **D2 / D3 / N1 / N2 (P3, ADDITIONS not defects):** add a lockfile *or* leave
   floor-only; SHA-pin CI actions; add 3.14 to the CI matrix *or* state "tested
   3.12–3.13"; gitignore `.mcp.json`. All optional polish.
7. **`_shared-context/AUDIT_LOG.md` cleanup (process, morning).** See the
   dedicated note at the end — my auditor subagents (and other parallel
   sessions') wrote rows there against the fence; I deliberately left it
   uncommitted and untouched.

Nothing was reverted — no fix derailed the suite.

## Verification record

- **READ phase:** 5 fresh-context `auditor` subagents, one concern each
  (coach-billing/money · data-loss & write fences · doc-drift/honesty ·
  security/secrets/deps · test-honesty), each spoon-fed the architecture +
  fences and required to return file:line evidence. Synthesis (dedupe, drop
  over-claims, severity-rank) was mine; I confirmed every fixed/parked finding
  by reading the code myself.
- **Codex (PRIMARY, read-only):** ✅ twice. On the underlying slice-17 *code*
  diff (run by the data-loss auditor: "runtime changes consistent", lone flag =
  the pre-commit nit, now FIXED). On **my fix diff** (`codex review --base
  f28a6d0`) it initially stumbled — assuming a `src/hevy_brain/` layout (this
  repo is `hevy_brain/` at root) — then **self-corrected**, read the actual
  changed files, re-ran `ruff` on the new tests (clean), grepped for stale
  `scripts/` references (none), and concluded: *"changes are limited to
  documentation, cleanup of obsolete scripts, pre-commit configuration, and
  additional regression tests. I did not identify any introduced correctness
  issues."*
- **Opus verifier (SECONDARY, fresh context):** ✅ **all 4 fixes CORRECT**, with
  file:line evidence AND *mutation proofs in a throwaway git worktree* — reverting
  the slice-17 ordering makes the billing test fail (`assert 0 == 1`); deleting
  the `check_budget` call site makes the budget test fail (returns 0, `billed==[1]`).
  Confirmed no broken references, docs factually accurate, 336 green, ruff+mypy
  clean. Verdict: "Nothing needs changing."
- **Adversarial:** the money findings (A1–A3) survived my own skeptical re-read;
  I *refuted* Auditor A's "doc overstatement" sub-claim (the slice-17 comment is
  precise) and down-scoped A1 to "bounded inherent soft cap".
- **Runtime smoke (tiny-real-input, offline, no Hevy account):**
  `python -m hevy_brain.cli --help` → dispatch loads, lists all 10 command groups;
  `… doctor` → **exit 0** (Hevy key set, vault OK, 285 workouts, synced 0.7h ago,
  vault built; only the optional Anthropic key WARNs); `… status` → **exit 0**
  (285 workouts / 29 measurements / 486 templates / 7 routines).

## Doc drift fixed
README "Use" block (3 missing commands) · PROMPT.md stale `Fitness/Hevy`. All
numeric/headline claims independently **re-verified TRUE** (see below) — only
these two drifted.

## What's healthy (verified clean — protect these)

- **Data-loss / irreversible-write fences — all NIL** under adversarial runtime
  probing: path jail (two layers — `sanitize_filename` `writer.py:26,33-37` +
  `_target` containment check `:56-61`; defeated `..`/abs/UNC/NUL/CON/unicode and
  hostile titles end-to-end), atomic writes (`mkstemp` same-dir + `os.replace`),
  marker preservation (line-anchored `^%% hevy-brain:end %%`), archive-not-destroy
  (collision-suffixed same-tree move), sync cursor rollback (in-place meta
  restore + meta-saved-LAST, `sync.py:191-217`/`cache.py:129-133`), PUT
  full-replacement (start/end times mandatory, no silent field drop).
- **Secrets — NIL** in all tracked files AND the full 160-commit history
  (`config.toml` never held a key; it is gitignored + untracked); keys flow
  env→header only, never logged; 4xx body-surfacing can't echo the request key.
- **Injection — NIL:** no `subprocess`/`eval`/`exec`/`pickle`; all YAML is
  `safe_load`; untrusted Hevy text becomes JSON-body fields, never path segments.
- **CI safety:** `pull_request` (not `_target`), no secrets referenced.
- **Knowledge bridge:** read-only, jailed, refuses `sources/` (tested).
- **Verified-TRUE claims:** 333 tests (now 336) · 88% coverage · mypy 41 files
  clean · `Hevy` default consistent across all sites · CI matrix 3.12+3.13 ·
  "writes to Hevy only via push" (all 5 mutating client methods reachable only
  from `writeback/` ← `push` handlers) · `_coach_recap` is live (not dead code).
- **Budget boundary correct** (`>=`, 0 refuses, no off-by-one); **money is an
  integer count** (no float); **free path cannot bill**; **no double-save
  clobber**; **`set_measurements` str-key change behaviour-neutral** for ISO
  data.

## Decisions I made for you (SAMRATH.md §3 defaults, stated)

- **Scoped the window to slice 17 + the surfaces it certifies**, not the full
  48h sprint (that's the full-repo audit's job; this prompt is "today's work").
- **Fixed the HA fork scripts by deletion** (not flagging) — they are dead,
  broken, and contradict the docs; on a revertible branch; I didn't create them
  (fork-inherited), so this is surfaced prominently as the headline change —
  `git revert 86df943` if you disagree.
- **Did NOT touch the coach billing code** — the money nuance (A1) is bounded +
  inherent and needs your taste call; "when in doubt, document, don't touch".
- **Added regression tests that pin existing-correct behaviour** (the slice-17
  fix + budget wiring) rather than changing code — pure hardening, green.
- **Left `_shared-context` untouched** (see below) — fence + live concurrent
  writers from other sessions.
- **Nothing pushed, nothing merged** — the branch is your morning decision.

## Lessons for _shared-context (note only — the roll-up is a morning job)

- **Auditor subagents with Bash will write outside their lane unless told twice.**
  Three of my read-only auditors wrote rows/sections to
  `C:\Users\samra\Atlas\repos\_shared-context\AUDIT_LOG.md` (and one stamped this
  repo's `HANDOFF.md`, which I reverted) despite the "read-only / don't touch
  `_shared-context`" framing. **The `_shared-context/AUDIT_LOG.md` working tree
  is now a collaborative uncommitted draft** containing my hevy-brain rows
  *intermingled with rows from the parallel mission-control and
  Cold-Turkey/MonkMode overnight sessions*. **I deliberately did NOT revert it** —
  a blanket `git checkout` would clobber those other live sessions' work, and a
  surgical edit risks racing their concurrent writes (the exact clash the fence
  exists to prevent). It is uncommitted; my session committed nothing there. The
  morning roll-up should reconcile the whole file. *Future overnight prompts:
  give subagents an explicit "READ-ONLY, do not write any file, return findings
  as text only" instruction.*
- Re-confirms the value of: persist-before-advance (the sync cursor fence held),
  atomic-writes, money-as-integer-count, fail-closed — none were violated by
  today's work.

## Carry-on (next session)

> **Overnight audit done 14/06/2026 — repo GREEN, fixes on branch
> `overnight-audit-2026-06-14` (4 commits, NOT pushed/merged), pre-audit
> `f28a6d0`.** 0 P0; the only real correctness nuance is the bounded `coach
> --api` soft-cap (A1) — your money-semantics call. **First:** review the branch
> diff (`git -C . diff f28a6d0..HEAD`) and either merge + push or cherry-pick;
> the doc/test/rot fixes are safe, the HA-script deletion is the one to eyeball
> (`86df943`). **Then decide** the parked list above (A1 accept-vs-harden, A2
> graceful save, D1 history rewrite as part of the pre-public checklist).
> **Morning cleanup:** reconcile `_shared-context/AUDIT_LOG.md` (it holds this
> session's + other sessions' uncommitted rows — don't lose the mission-control /
> MonkMode entries). Both verify passes (Codex + Opus verifier) came back clean.
> Locked, unchanged: offline
> tests only; explicit-push fence; repo private until key rotation → flip is your
> call. Pipeline confirmed alive (sync 0.7h ago, vault built).
