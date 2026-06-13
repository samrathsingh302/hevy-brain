---
status: done
agent: slice17-builder-1
goal: "Slice 17: Tier-1 pre-public hardening — fix audit-found drift/correctness + add portfolio-grade tooling (CI matrix, coverage, mypy, pre-commit)"
outcome: "Audit-driven fixes (README test count 60->333, config subfolder default Fitness/Hevy->Hevy, coach --api budget-integrity ordering) + tooling (CI 3.12+3.13 matrix, 88% coverage, mypy clean across 41 files, pre-commit mirroring CI). 333 offline tests (was 332), ruff + mypy clean. Pure offline/CI work — no live account interaction. Preceded by a 3-lens 'what else' research pass (values/audit/opportunities) whose full backlog is recorded below."
gotchas: "README test count will keep drifting every slice (now 333 + '88% coverage'); the audit suggested dropping the absolute number, but the concrete figure reads well to recruiters — accept the drift or genericise later. config default fix has TWO sites: the dataclass field AND load_config's vault.get(...) fallback — change both or they disagree. coach --api: store.save() is now called twice on the metered path (once to persist the billed call immediately, once inside _save_focus for the snapshot) — intentional, correctness over a micro double-write. mypy is config-driven via [tool.mypy] files=['hevy_brain'] so CI/pre-commit run bare `mypy` (no args); ignore_missing_imports=true because aiohttp/anthropic/yaml ship partial/no stubs — we type our code, not theirs. mypy scoped to hevy_brain only (NOT tests). Two mypy fixes were needed: `today: date` on the extracted _coach_recap helper, and a str-keyed dict in CacheStore.set_measurements (sorted() rejected Any|None keys). _coach_recap was extracted purely to keep _cmd_coach under ruff's PLR0915 (50-statement) limit after adding store.save()."
carry-on: "Solo-buildable next: B1 per-lift progression targets (~M), or Tier-3 features (deload flag / volume landmarks / consistency heatmap / doctor vault-drift check / export / diff). User-gated: live-prove slice 12 adherence capture; pre-public checklist (key rotation -> flip). E4 stays atlas-pipeline."
---

# 13/06/2026 — Slice 17: Tier-1 pre-public hardening

After the roadmap's feature sections (A/C/D) were drained, a deep "what else"
pass was run, then the highest-leverage cluster built: the things that gate the
repo being a credible CV/portfolio piece.

## The "what else" research (3 lenses, read-only)

Fanned out three agents and synthesised:
- **Values (shared-context):** hevy-brain is a CV piece — polish/CI/docs *are*
  features; free-tier; no data loss; simplicity; honesty discipline. Avoid:
  paid services, flipping public myself, publishing body data, over-production.
- **Audit (correctness/rot/security):** no P0/P1; safety surfaces solid. P2s:
  README test count, config subfolder default, coach --api ordering, a couple
  defensive/unreachable nits.
- **Opportunities:** CI already exists; missing mypy/coverage/3.12-matrix/
  pre-commit; B1 (per-lift progression targets) is the one genuinely-missing
  feature; plus a menu of in-spirit Tier-3 ideas.

Full tiered backlog is in this slice's commit messages + the carry-on.

## Done (commits 606791b correctness, c2bb72c tooling — pushed)

1. **Correctness / doc-drift** (`606791b`):
   - README "60 pytest tests" → 333 (×2). (124 exercises / 486 templates
     verified *correct* — left as-is.)
   - `config.vault_subfolder` default `Fitness/Hevy` → `Hevy` (dataclass +
     `load_config`); regression test `test_vault_subfolder_defaults_to_hevy`.
   - `coach --api`: `record_call` + `store.save()` now run **before** the
     focus-snapshot save, so a later save failure can't lose the billed-call
     count and let the budget guard over-bill.
   - Extracted `_coach_recap` (memory + adherence recap) from `_cmd_coach` to
     stay under the 50-statement lint cap; behaviour identical.
2. **Tooling** (`c2bb72c`):
   - CI `test.yml` matrix **3.12 + 3.13**; pytest with `--cov` (**88%**).
   - **mypy** `==2.1.0` + `[tool.mypy]` (files=hevy_brain, ignore_missing_imports)
     wired into `lint.yml`; clean across 41 files (fixes: `today: date`,
     str-keyed `set_measurements`).
   - `pytest-cov` dev dep; `.pre-commit-config.yaml` (ruff + mypy, pinned).

## Verify

`python -m pytest tests -q` → **333 passed** (88% cov) · `python -m ruff check
hevy_brain tests` → clean · `python -m mypy` → clean (41 files). No live
account interaction (offline + CI only).

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **Build the hardening cluster first** — a private/drifted repo can't be a
  portfolio piece; the values lens ranked this #1.
- **mypy lenient-but-green** (`ignore_missing_imports`) — type our code, not the
  unstubbed deps; tighten incrementally later rather than chase stubs now.
- **Keep concrete test/coverage numbers in README** — reads well to recruiters,
  accept the per-slice drift.
- **Didn't touch** the unreachable/defensive audit nits (future week_count
  guard, missing-`id` KeyError, log rotation) — not worth churn now.

## Watch / gotchas

- README numbers drift each slice; config default lives in two sites; mypy is
  config-driven (run bare); coach --api saves twice by design (see frontmatter).
- `HevyBrain Coach` still pending first fire (next Sun 14/06 19:00 — tomorrow).

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice17-hardening.md) and the roadmap. Quick check: did
> `HevyBrain Coach` fire Sunday 14/06 19:00 (`logs\coach.log` /
> `Get-ScheduledTaskInfo`)? Roadmap A/C/D + Tier-1 hardening are done. Pick a
> **solo-buildable** slice: **B1 per-lift progression targets** (recommended —
> "next time try X kg × Y" on exercise notes from `epley_1rm` + `weekly_overload`;
> ~M), or a Tier-3 feature (deload-readiness flag, volume-landmark/MEV check
> labelled general-knowledge, consistency heatmap reusing the chart renderer,
> `doctor` vault-drift check for edits above the marker, `export --csv`, `diff`
> last-vs-prior session). **User-gated** (confirm before acting): live-prove
> slice 12's adherence capture (push a guide draft, train, coach); pre-public
> checklist (rotate `HEVY_API_KEY` → flip visibility — Samrath's explicit call).
> Offline tests with fixtures, ruff + mypy clean, one slice, commit per coherent
> step, push at end, update HANDOFF + dated handoff + carry-on. Locked:
> explicit-push fence; vault offline-rebuildable (only `verify` makes a
> read-only network call); free tiers; read-only knowledge bridge; body data off
> anything published; repo private until key rotation. E4 stays atlas-pipeline.
> Do not re-litigate.
