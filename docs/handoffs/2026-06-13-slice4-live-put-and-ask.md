---
status: done
agent: slice4-builder-1
goal: "Slice 4: live write-path verification (first real PUT) + C2 `hevy-brain ask`"
outcome: "PUT live-verified end to end (upper → Return Week 1 — upper, 200 OK, round-trip synced); 4 write-path fixes; `ask` shipped with question-driven retrieval; 161 offline tests green (was 135), ruff clean"
gotchas: "Hevy PUT: empty-string notes → 400, MISSING notes key = clear notes (omission semantics confirmed live). The managed marker only counts at line start now — never rely on substring checks. Ask notes carry a 6-hex question digest in the filename. The hevy-brain.exe console script is stale (ModuleNotFoundError) — use `python -m hevy_brain.cli` until reinstalled."
carry-on: "E2 `guide redesign` (honesty-labelled until E4) or F3 workout fix-up; E4 ingestion stays an atlas-pipeline task"
---

# 13/06/2026 — Slice 4: live write path + `ask` (C2)

## Done (commits 96442da → 381efa3, pushed)

1. **Live write-path verification** — the slice-3 carry-on's first item:
   - Dry-run on `Drafts/Return Week 1 — upper.md` → clean diff (title +
     5 exercises at 60%, 0 kg exercises untouched, notes untouched).
   - Restore file secured first: `Drafts/RESTORE upper (original).md`.
   - **First real PUT, with Samrath's explicit go: 200 OK.** Routine `upper`
     is now `Return Week 1 — upper` in Hevy at week-1 loads. `full` confirmed
     the round-trip; a post-fix dry-run reports "no changes" (exact
     round-trip equality against the live server).
2. **Four fixes from the verification** (`96442da`), all live-verified:
   - The PUT initially failed 400: Hevy rejects `"notes": ""`. Confirmed
     empirically that omitting the key CLEARS notes server-side (true full
     replacement) — so `parse_routine_note` omits empty notes, drafts keep
     carrying real notes (slice-3 rule unchanged), and deleting the notes
     line is the legitimate "clear notes" path.
   - `api/client`: 4xx errors now carry the server's response body
     (`API error 400: {"error":...}`); 5xx stays a communication error.
   - `cli`: stdout/stderr reconfigured `errors="replace"` — the diff
     preview's `→` crashed cp1252 consoles mid-print (the first dry-run
     died half-way).
   - `vault`: `archive_stale_routine_notes` sweeps managed routine notes no
     active routine owns — the rename had orphaned `Routines/upper.md`
     forever (store only remembers deletions). User files and `Drafts/`
     are never touched; live-verified (`upper.md` → `Archive/`).
3. **C2 `hevy-brain ask "…"`** (`381efa3`): `coach/ask.py` +
   `_cmd_ask`/`_load_knowledge_for_question` in the CLI. Free briefing to
   `Coach/<date> Ask — <slug> (<digest>).md`: question + ask-specific coach
   prompt (shared `PROVENANCE_RULES`) + full `advisor.build_context` data
   pack + question-driven claims (topics named in the question → term
   pattern via claims-index/grep → config-topic fallback), deduped, with a
   one-line honest retrieval summary (flags aborted retrieval). No API
   call; no new config. Live: 223 claims for a bench+sleep question,
   re-ask reuses the note byte-identically.
4. **Verifier fixes (pre-commit, fix-first verdict):**
   - **Marker-mention split (MAJOR, latent everywhere):** briefing callouts
     quote `%% hevy-brain:end %%` in backticks; `VaultWriter.write` split at
     the first *substring* hit, so every regen duplicated the note body
     (repro: 3 writes → 3× content). Now split on the first LINE-ANCHORED
     marker. This also protected the coach + guide briefings.
   - **Slug crash (MAJOR):** one 100+ char word defeated word-boundary
     truncation → unbounded filename → uncaught `WinError 123`. Slugs
     hard-cut; paths append a 6-hex digest of the normalised question so
     two questions whose slugs collide never share (rebind) a note, while
     case/punctuation variants of the same question still do.

## Verify

`python -m pytest tests -q` → **161 passed** (was 135) · `python -m ruff
check hevy_brain tests` → clean. All offline. Live: PUT 200 + round-trip;
ask × 2 runs → one stable note.

## Decisions taken (SAMRATH.md §3 defaults, stated)

- **`ask` is free-path only** this slice (no `--api` structured variant);
  the metered path can reuse `generate_report` later if wanted.
- **No new config** for ask: base topics reuse `[knowledge] topics`.
- **Fallback retrieval**: when neither topics nor terms match, the config
  topics load as the pack (summary says so) — never a silently empty pack.
- **"back" is not a stopword** (muscle group beats "get back into it").
- **Hash suffix on ask filenames** (parenthesised, like routine id
  suffixes) — chosen over collision detection for determinism.

## Watch / gotchas

- **Hevy is now running the week-1 `upper` routine.** Restore = push
  `Drafts/RESTORE upper (original).md` (also archived copy at
  `Archive/upper.md` after the sweep). The other two drafts (`push 1`,
  `pull 1`) are still unpushed.
- The stale-sweep treats everything at `Routines/*.md` with the managed
  marker + `type: hevy-routine` as hevy-brain's; user copies of managed
  notes belong in `Drafts/` (documented behaviour, now enforced).
- `hevy-brain.exe` (pip console script) is stale → `ModuleNotFoundError`;
  `python -m hevy_brain.cli` works. `pip install -e ".[dev]"` again to fix.
  The scheduled tasks run script logic, so check they still execute.
- PowerShell sessions here don't inherit User-scope env vars: load with
  `[Environment]::GetEnvironmentVariable('HEVY_API_KEY','User')`.

## Carry-on prompt (next session)

> Read CLAUDE.md + HANDOFF.md, then the newest dated handoff
> (2026-06-13-slice4-live-put-and-ask.md) and the roadmap
> `C:\Users\samra\Atlas\projects\hevy-brain-roadmap.md`. Quick checks
> first: confirm the `HevyBrain Sync`/`HevyBrain Coach` scheduled tasks
> still run (the stale `hevy-brain.exe` shim suggests the env drifted —
> re-run `pip install -e ".[dev]"`), and note Hevy is currently on the
> week-1 `upper` routine (restore file in `Routines/Drafts/`). Then build
> the next slice — recommended: **E2 `guide redesign`** (split/volume/
> plateau detection from cache → redesign briefing + routine drafts; works
> day one with honesty labels, corpus-grounded only after E4 ingestion,
> which is an atlas-pipeline task, not this repo) or **F3 `push workout
> --update`** (fix a logged workout from its note; small). Offline tests
> with fixtures, ruff clean, one slice, commit per coherent step, push at
> end, update HANDOFF + dated handoff + carry-on. Last commit: see HANDOFF.
> Locked: explicit-push fence; free tiers; read-only knowledge bridge
> (never write pipeline folders, never read sources/); repo private until
> key rotation. Do not re-litigate.
