# hevy-brain — verify & close out the overnight-audit branch (14/06/2026)

> **Hand this to a fresh hevy-brain session.** Verify-then-act brief. Samrath drives merge/push; you do the verification and the safe fixes. **Trust the live repo, not the numbers in this brief — re-derive every count yourself.** This brief was written from the vault side at ~16:00 on 14/06 and is **already substantially stale** (see §0): unlike the other four repos, hevy-brain's overnight branch was *merged and pushed the same morning*. Read §0 before doing anything.

## 0. Why this exists (and why it's already mostly done)
The overnight autonomous audit (`docs/handoffs/2026-06-14-overnight-audit.md`) ran at ~05:28 and left 4 fix commits on branch `overnight-audit-2026-06-14`. **Then a morning session (this repo only) picked up the audit's decision list and closed it out** (`docs/handoffs/2026-06-14-morning-merge-a1a2.md`): it actioned the two parked money/robustness items per Samrath's calls, **fast-forward-merged `overnight-audit-2026-06-14` into `main`, and PUSHED to origin**.

So unlike mission-control / the other repos, **there is no unmerged audit branch waiting on you here.** `main` *is* the merged audit. Your job is the lighter one:
1. **Re-confirm** the merged state on `main` is genuinely GREEN (gates + a runtime smoke), because a green suite at merge time is not proof it still holds.
2. **Resolve the ONE genuinely-uncommitted thing** left in the working tree — the parked `ruff format` drift (28 files, cosmetic) — by either committing it or discarding it (Samrath-flavoured but low-stakes; see §4).
3. **Note** the still-parked pre-public items (D1 history rewrite, key rotation, public flip) without re-doing them — they're Samrath/§4-gated and already tracked.
4. Do **not** re-litigate the money decision (A1) — Samrath already decided it (accept + document). Do not touch `_shared-context`.

**The hard-verification target here is the smallest of the five**, because this repo also carries the *least* Codex debt: Codex ran AND a fresh Opus verifier ran (mutation-proven) on both the overnight fixes and the morning A1/A2 fixes. Re-confirmation, not re-litigation.

## 1. Orient (read in this order)
1. `CLAUDE.md` (fences) → `HANDOFF.md` → `docs/handoffs/2026-06-14-morning-merge-a1a2.md` (the authoritative carry-on — newest) → `docs/handoffs/2026-06-14-overnight-audit.md` (the audit report) → `C:\Users\samra\vault\_shared-context\` SAMRATH.md + ORCHESTRATION.md (+ the Codex/Opus two-pass doctrine).
2. **Re-derive the live git state** (do not trust the snapshot below — confirm it):
   - `git -C "C:/Users/samra/repos/HA-hevy" log --oneline --decorate --graph -15`
   - `git -C "C:/Users/samra/repos/HA-hevy" status`
   - `git -C "C:/Users/samra/repos/HA-hevy" rev-list --left-right --count main...overnight-audit-2026-06-14`
   - `git -C "C:/Users/samra/repos/HA-hevy" diff --stat f28a6d0..overnight-audit-2026-06-14`
   - `git -C "C:/Users/samra/repos/HA-hevy" merge-base --is-ancestor overnight-audit-2026-06-14 main && echo MERGED` (expect MERGED)

**Snapshot as of 14/06 ~16:00 (VERIFY it still holds — every number here was re-derived from the live repo when this was written):**
- **Base (pre-audit) = `f28a6d0`** (`prompt: drop nonexistent Fable-5 model reference`). This is the audit's `pre_audit_commit`. (NB: this is *not* a hash to flip the repo public — see §5.)
- Branch `overnight-audit-2026-06-14` tip = **`37f625c`**; **8 commits** sit on it above `f28a6d0` (4 overnight fixes + the report-doc + 3 morning commits — list in §2). `git rev-list --left-right --count main...overnight-audit-2026-06-14` = **`1  0`** (main is **1 ahead, 0 behind** the branch tip).
- **`main` = `origin/main` = `cb6b9e0`** (`docs: dated handoff for the 14/06 morning session`). The audit branch is **fully merged into main** (ff) **and pushed**. The one commit `main` has beyond the branch tip is the morning dated-handoff pointer (`cb6b9e0`).
- ⚠ **Working tree is dirty: 28 modified files, all in `hevy_brain/` + `tests/`, ALL uncommitted.** This is the parked **`ruff format` drift** — it is *pure reformatting* (line-regrouping; `ruff format --check` reports the tree "already formatted", i.e. someone ran `ruff format` and never committed it). It is **not** a logic change, **not** a stash, **not** lost work. Decide it per §4 — do not panic-commit or blind-discard it.

## 2. The branch (labels are claims — re-verify each)
Base = `f28a6d0`. `git diff f28a6d0..overnight-audit-2026-06-14` is the full review surface (12 files, ~481/45). Since it's all already on `main`, you can equally review `git diff f28a6d0..cb6b9e0` to include the morning handoff commit. **Every commit below predates ~17:00 14/06; none postdate the morning close-out**, so there is no "added after the report, never verified" commit to fear here (contrast mission-control). Order, newest first:

**Morning close-out commits (added AFTER the overnight report — verified by the morning session's own two-pass, re-confirm anyway):**
- `37f625c` (docs) morning 14/06 — A1/A2 actioned, branch merged; HANDOFF + CHANGELOG
- `aba321a` **gitignore** Claude Code local-settings + `.mypy_cache` (Codex P3 catch)
- `586a42e` **fix(coach): graceful OSError on both coach paths + A1 soft-cap doc** — the substantive morning change. A2: `except (CoachError, OSError)` on the `--api` path + wrapped write/save on the free path; **+2 regression tests** (mutation-proven). A1: a comment block at the bill site documenting the budget as a best-effort *soft* cap. `VaultPathError` (path-jail) is **deliberately not caught** — safety stop, not IO. **This is the one to eyeball hardest** (it's the money file).

**Overnight audit fix commits (covered by the overnight Codex + Opus verifier per the report):**
- `0fcdba8` (docs) the overnight audit report + HANDOFF/CHANGELOG pointers
- `2ba88a3` **test:** +3 regression tests — budget guard, billing-ordering, config dataclass default (no `hevy_brain` source changed)
- `8e7fd62` **chore:** drop stray `args: ["check"]` from the pre-commit ruff hook (it made `ruff check check` → E902)
- `55cda72` **docs:** README +`doctor`/`verify exercise`/`guide redesign`; `PROMPT.md` subfolder build-note (CV-bound doc drift)
- `86df943` **fix:** remove Home-Assistant fork-leftover `scripts/setup` + `scripts/develop` (dead, broken, contradicted the docs) — the headline change; `git revert 86df943` if Samrath ever disagrees, but it's already merged.

**Note the drift vs the vault roll-up:** the roll-up said "~4 fix commits". The *audit itself* made exactly 4 fix commits (`86df943`, `55cda72`, `8e7fd62`, `2ba88a3`) — accurate. The branch now carries **8** because the morning close-out (3 commits) was layered on before merge. Re-derive and don't be alarmed by the larger number.

## 3. Verify — two-pass + runtime smoke, over the merged surface `f28a6d0..main`
Because it's already merged, verify on `main` (the live state Samrath shipped). A green suite is **not** proof it still works — add the runtime smoke.

1. **Gates (re-derive the numbers — do NOT quote mine):** with the working tree as-is, then again with it clean if you discard the format drift:
   - `pip install -e ".[dev]"` then `python -m pytest tests -q` — the morning handoff claims **338** offline tests (the audit's 336 + the 2 morning A2 regression tests). **Re-derive; report the actual count.**
   - `python -m ruff check hevy_brain tests` (CI gates this — expect clean).
   - `python -m mypy` (expect clean; mypy scans `hevy_brain` only).
2. **PRIMARY = Codex** (read-only — **this repo carries the LEAST Codex debt**; both the overnight fixes and the morning A1/A2 fixes already passed Codex). Re-run only if you want fresh eyes on the merged whole: `codex review --base f28a6d0`. **Never** let it write/apply/commit; **never** feed it vault or transcript content. If it's rate-limited, log the command and move on — you are re-confirming, not clearing a debt.
3. **SECONDARY = fresh-context Opus `verifier` subagent** over `f28a6d0..main`, against each fix's *intent* — especially `586a42e` (the coach OSError handling: does a disk/IO failure on **both** the free and `--api` paths now print "Coach failed" and return 1, while `VaultPathError` still propagates uncaught?). Hunt edge cases, not a diff restatement. The morning verifier already proved the 2 new tests fail against the old code by mutation — sanity-check that claim, don't just trust it.
4. **RUNTIME SMOKE (offline, NEVER the real account — see §6):**
   - `python -m hevy_brain.cli --help` → dispatch loads, lists all command groups.
   - `python -m hevy_brain.cli doctor` → expect **exit 0** (real env: ~285 workouts cached, synced recently, vault built; only the optional Anthropic key WARNs).
   - `python -m hevy_brain.cli status` → exit 0.
   - **Free `coach` path** (the one the scheduled task fires Sun 19:00): the morning session smoked it to exit 0 (briefing written, recap). If you re-run it, it idempotently regenerates today's note — fine. **Do NOT run `coach --api`** (it bills) and **do NOT** exercise any `push` (that writes to Hevy).

## 4. Action the remaining items (one real fix-decision; the rest are already decided or §4-gated)
- **`ruff format` drift (28 files, uncommitted) — the ONE thing actually open.** It's pure cosmetic reformatting; CI gates `ruff check` only, so `main` is GREEN with or without it. **Two clean options — surface the choice to Samrath if unsure, it's his repo aesthetic:**
  - **(a) Commit it** as a single `style: ruff format hevy_brain tests` commit (no logic change; run the full suite after — expect the same count, all green — to prove formatting changed nothing), then it's done forever and the pre-commit ruff-format hook stops nagging. **Recommended** — it's the lowest-friction permanent fix and the tree is already in the formatted state.
  - **(b) Discard it** (`git restore .`) if Samrath would rather format land inside a real feature commit later. Lossless — `ruff format` reproduces it on demand.
  - Either way: **do not merge/push without Samrath's go** (§6), and do not bundle it with anything else.
- **A1 (coach `--api` soft cap) — ALREADY DECIDED, do not re-open.** Samrath's call was **accept + document**; the comment block landed at the bill site in `586a42e`. *(Framing, for context only — you are not deciding this:* the guard can't be a hard cap because Anthropic bills server-side the instant `messages.parse()` returns, before any local count saves. **Blast radius is tiny:** single-user personal CLI, sub-second crash window, at most `max_per_day` — default **4** — extra Opus calls on an affected day. That's why "accept + document" was the right call and there's nothing to harden.* )* If Samrath ever revisits and wants the hard-cap variant (write a provisional "attempted" stamp before `generate_report`, reconcile on success), that's a *new* slice with a regression test — not part of this close-out.
- **A2 (graceful coach-save failure) — ALREADY FIXED** in `586a42e` (+2 tests). Just confirm in §3.2/§3.4.
- **Parked, Samrath/§4-gated — surface, do NOT do:** **D1** `config.toml` lives in 4 historical commits (username + an old vault path, **no API key ever**) → clearable only by a history rewrite, which is pre-flip + irreversible = Samrath's call (already item 2 of the HANDOFF pre-public checklist). **Pre-public flip** itself (rotate `HEVY_API_KEY` → `gh repo edit --visibility public`) = a Samrath §4 call (money/irreversible/public exposure). Leave both for him.

## 5. Already handled, don't redo — and `_shared-context` is OFF-LIMITS
- **The branch is already merged + pushed.** Do not re-merge, do not re-push, do not delete the `overnight-audit-2026-06-14` ref without asking (it's a harmless ancestor of `main` now).
- **A standalone pre-public secrets/injection audit already cleared this repo as "safe to flip public."** The overnight report verified secrets/injection/data-loss fences all NIL across the full history (`config.toml` never held a key; keys flow env→header only). **Do NOT re-run a secrets sweep.** The *only* pre-flip action is **rotate `HEVY_API_KEY`** (standing lesson: any key that's appeared in a chat is burned), and the flip itself is a **separate** Samrath call — both already in the HANDOFF checklist. Mentioned here only so you don't redo the audit.
- **`_shared-context` is OFF-LIMITS.** The overnight `AUDIT_LOG.md` cross-write incident the report flags was **already reconciled by the vault session**, and `_shared-context`'s `main` already carries the reconciled AUDIT_LOG + guard-hardening commits on **Samrath's** push gate. **Do NOT touch `C:\Users\samra\vault\_shared-context` at all** — not to read-fix, not to roll up, not to commit.

## 6. Fences (hevy-brain `CLAUDE.md` — no later reasoning overrides these)
- **Never hit the real Hevy account in tests** — sync/push tests stay **offline by design** (fixtures/mocks only). Runtime smoke uses read-only/offline commands; **never** run `push` or `coach --api` during verification.
- Never write outside the `Hevy/` vault subfolder (path-traversal guard) · no non-atomic vault writes · never overwrite user edits below the `%% hevy-brain:end %%` marker (preserve on regen) · never delete a workout note (archive to `Archive/`, never destroy).
- The Hevy key lives **only** in the `HEVY_API_KEY` env var — never in config, never in git. Data/cache/notes stay gitignored, never committed.
- Writes to Hevy happen **only via explicit `push` commands** — never auto-write.
- Free tiers / £0. Commit per coherent step. **Push / merge to `main` on Samrath's go only** — do NOT push or merge yourself (and `main` is already pushed here, so there should be nothing to push beyond an optional format commit *he* approves).

## 7. Definition of done
☐ live git state re-derived (confirm `overnight-audit-2026-06-14` is an ancestor of `main`; main = origin/main = `cb6b9e0`; base `f28a6d0`) · ☐ merged surface `f28a6d0..main` re-confirmed GREEN: gates green (test count re-derived — expect ~338), Codex re-run *or* its low-debt status logged, fresh Opus verifier pass, runtime smoke (`doctor`/`status`/free `coach` exit 0, NO real-account calls) · ☐ `586a42e` (coach OSError + A1 doc) specifically eyeballed · ☐ the **uncommitted `ruff format` drift resolved** — committed (recommended) or discarded, suite still green either way, **not** pushed without Samrath's go · ☐ A1/A2 confirmed already-done, **not** re-litigated · ☐ D1 + key-rotation + public-flip left for Samrath (surfaced, not actioned) · ☐ **nothing pushed without Samrath's go**, **`_shared-context` untouched**, real Hevy account never hit.
