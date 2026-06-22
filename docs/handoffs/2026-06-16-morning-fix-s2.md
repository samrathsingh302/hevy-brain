# 2026-06-16 — Morning fix run §2: HA-hevy vault-writer resilience + CSV-injection

Second §2 batch of the 16/06 morning-fix run, continuing
`2026-06-16-morning-fix-warmup-cachelock.md` (the two P1s, commit `eb63d28`).
Branch `fix/morning-2026-06-16`. Both fixes verified and committed locally.
**NOT pushed — push is Samrath's gate.**

## What was fixed

### C1 — vault writer per-note resilience · commit `722099f`
`vault/writer.py` had no resilience against a locked note: a single
`PermissionError` (e.g. a note open/locked elsewhere) would abort the entire vault
rebuild. Fix: **bounded retry** on the locked-note `PermissionError`, then **skip and
record** rather than aborting. `build_vault` now surfaces the skipped notes via
`changed['skipped']`, so the rest of the rebuild completes and the skip is visible.

### C5 — CSV formula-injection neutralised · commit `5491ab4`
`export.py` wrote exported titles to CSV without neutralising spreadsheet formula
injection (a leading `=` / `+` / `-` / `@` in a user title executing on open). Fix:
a `_csv_safe` helper that neutralises CSV formula injection in exported titles.

## Verification record
- **Tests 456 → 458** (+2); **ruff + mypy clean**.
- **Fresh-Opus verifier verdict: SHIP** on both commits.

## Codex debt (Codex was OUT this session)
Per Samrath's standing call, Codex review is deferred. Re-run once credits are topped up:

```
codex review --commit 722099f
codex review --commit 5491ab4
```

## Not done / needs Samrath
- **PUSH** `fix/morning-2026-06-16` — Samrath's gate (LOCAL-ONLY, not pushed).
- Remaining audit items from `03-FIXES.md` §2/§3 not covered here stay as listed in the
  warm-up/cache-lock handoff's "Not done / gates" section (UTC→Europe/London calendar-day,
  coach `--api` persist-order, empty-routines/measurements guard, corrupt-cache guard,
  `anthropic>=0.40` floor).
- Pre-existing uncommitted edits (`CLAUDE.md`, `HANDOFF.md`,
  `docs/VERIFY-AND-CLOSEOUT-2026-06-14.md`) were left untouched — they predate this run.
