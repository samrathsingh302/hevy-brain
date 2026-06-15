---
status: done
agent: interactive-2026-06-16
goal: "Samrath asked for (a) clear the Codex S3-S6 verification debt IF its usage window has reset, and (b) fix the long-parked warm-up-set bug (best_e1rm_kg counted warm-up sets -> detect_plateaus could fire on an all-warm-up history) as a supervised slice."
outcome: "(a) Codex STILL rate-limited (confirmed empirically 16/06 -> 'try again 17/06 19:17'); debt NOT cleared, re-logged. (b) FIXED + pushed (f581b81): prs._session_entry + reconcile.aggregate_server now exclude warm-up sets from best_e1rm_kg / best_set; 444->449 tests (+5, red-before-green proven), ruff + mypy clean; fresh Opus verifier SHIP; live verify-exercise smoke reconciles exactly on the real account (0 drift). Codex primary on f581b81 deferred to the same reset."
branch: main
pre_session_commit: 05af146
fix_commit: f581b81
carry-on: "see below"
---

# Warm-up-set bug fix + Codex-debt check — hevy-brain — 16/06/2026

Interactive supervised session. Samrath picked two follow-ups from the "what's
left" readout: (a) clear the Codex debt if its window reset, (b) fix the
warm-up-set bug. Neither touches a SAMRATH.md §4 gate (offline analytics, no
Hevy write, no publish).

## (a) Codex S3–S6 verification debt — NOT cleared (still rate-limited)

Probed empirically: `codex review --commit 47bc97c` returned
`ERROR: You've hit your usage limit ... try again at Jun 17th, 2026 7:17 PM`
(exit 1). Codex CLI itself is healthy (`codex-cli 0.139.0`, provider openai,
model gpt-5.5) — it is the **usage window**, not the install. Matches the
overnight estimate exactly. **Debt stands**; re-run on/after **17/06 19:17**:

```
codex review --commit 47bc97c   # S3 export --csv
codex review --commit 109029e   # S4 diff
codex review --commit a555e2d   # S4 fix
codex review --commit 49506b0   # S5 deload
codex review --commit 37ac636   # S5 fix
codex review --commit 6bd38ac   # S6 landmarks
codex review --commit 622f08f   # S6 fix
codex review --commit f581b81   # this session's warm-up fix (see below)
```

(S1+S2 already had a full Codex pass overnight; the Opus verifier was the
load-bearing pass for S3–S6 and for f581b81.)

## (b) Warm-up-set bug — FIXED (`f581b81`)

**Root cause (confirmed at `prs.py:17-35`):** `_session_entry` looped over
`exercise["sets"]` with no warm-up filter, so `best_e1rm_kg` and `best_set`
were taken over every set including warm-ups. Because both are a **MAX** and
warm-ups are lighter, this only bites for an **all-warm-up** (or mislabelled)
history — there `best_e1rm_kg` was a positive warm-up-derived value, so
`detect_plateaus` (`patterns.py:149-151`) could fire on warm-up-only history,
and a progression target (which keys off `best_set`, `progression.py:52-55`)
could be computed from a warm-up.

**The fix (one concern, two tightly-coupled files):**
- `prs._session_entry` skips `s.get("type") == "warmup"` when computing
  `best_e1rm`/`best_e1rm_set`. An all-warm-up session now reads
  `best_e1rm_kg = 0.0`, `best_set = None` — **already a handled state**
  (bodyweight-only exercises produce it via `epley_1rm` returning 0; every
  downstream consumer already tolerates it: `progression.py:52` `or {}`,
  `sessiondiff.py:140-145` `if best:`, `patterns.py:151` `best_prior > 0`
  guard — the exact mechanism that now kills the false plateau).
- `reconcile.aggregate_server` mirrors the rule so `verify exercise` shows
  **no false drift**: warm-ups are excluded from the server **1RM estimate
  only**, but still counted toward `best_weight` and `total_volume` — matching
  the cache's `max_weight_kg`/`volume_kg` (`models.py:39,53`), which include
  every set. The live payload keys the type `set_type`; the nested-event shape
  may use `type` — `(s.get("set_type") or s.get("type"))` honours both.

**Deliberately out of scope (reported, not fixed):** `top_weight_kg` /
`max_weight_kg` still include warm-up weight, so an all-warm-up exercise can
still register a *weight* PR. Fixing that means changing `models.py`'s volume/
weight aggregation — much larger blast radius (charts, year-in-review totals,
all volume analytics). A separate slice if wanted.

## Verification (two-pass + runtime smoke)

- **Tests 444 → 449 (+5):** warm-up exclusion (mislabelled heavy warm-up not
  chosen), all-warm-up no-plateau **regression**, server-side mirror, no-false-
  drift reconcile on an all-warm-up exercise, nested-event key fallback.
- **Red-before-green proven:** `git stash` of `prs.py` alone → the two analytics
  tests FAIL (`best_e1rm_kg == 0.0` → False, warm-ups counted) → popped, restored.
- **ruff + mypy clean** (47 source files).
- **PRIMARY (Codex):** deferred — rate-limited (above). Debt logged.
- **SECONDARY (fresh Opus verifier):** **SHIP** — verified all three spec points
  at `file:line`, every ripple consumer None/0-safe, reconcile weight/volume
  asymmetry sound, dual-key handling correct, scope held. Suggested one optional
  test (nested-event key fallback) — folded in.
- **Live runtime smoke (read-only):** `verify exercise "Incline Bench Press
  (Dumbbell)"` reconciles **exactly** against the real account — 131 sessions,
  84 kg, 96.27 e1RM, 185,262 kg, **all rows ok, 0 drift, exit 0**. Proves the
  reconcile change is sound end-to-end on real data.

## Carry-on
> hevy-brain is GREEN on `main`, pushed: **449 tests**, ruff + mypy clean, 47
> source files. This session fixed the warm-up-set bug (`f581b81`) and confirmed
> the Codex debt is still blocked until **17/06 19:17**. **Next, on/after 17/06:**
> clear the Codex debt — run the 8 `codex review --commit` commands above
> (S3–S6 + f581b81), read-only, never `--fix`. **Remaining feature work** is just
> the deferred `doctor` vault-drift check (solo-buildable, do as `vault --dry-run`
> per the overnight plan §7). **Everything else is §4-gated / your call:**
> pre-public flip (rotate `HEVY_API_KEY` → `gh repo edit --visibility public`,
> D1 history rewrite, close dependabot #1/#2/#5); live-prove slice-12 adherence
> capture (push a guide draft + train it + coach); `_shared-context` AUDIT_LOG
> reconcile; E4 (atlas-pipeline). Known-but-deferred: warm-up *weight* PRs via
> `top_weight_kg` (separate slice); `config.py` bare KeyError on a malformed
> `[landmarks.bands]` entry (matches fail-loud posture). Locked, do not
> re-litigate: explicit-push fence; vault offline-rebuildable; free tiers;
> general-knowledge label on S5/S6; body data off published surfaces.
