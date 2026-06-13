"""Command-line interface for hevy-brain."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import aiohttp

from .api.client import HevyApiClient
from .config import Config, load_config
from .store.cache import CacheStore
from .sync import sync
from .vault.build import build_vault
from .vault.writer import VaultWriter

LOGGER = logging.getLogger("hevy_brain")


def _configure_output() -> None:
    """Never crash on printing.

    Windows consoles often default to cp1252, which cannot encode characters
    the diff preview uses (e.g. '→').
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def _require_api_key(config: Config) -> str:
    key = config.hevy_api_key
    if not key:
        print(
            "HEVY_API_KEY is not set. Get a key at "
            "https://hevy.com/settings?developer and set the env var.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return key


async def _with_client(
    config: Config, runner: Callable[[HevyApiClient], Awaitable[int]]
) -> int:
    key = _require_api_key(config)
    async with aiohttp.ClientSession() as session:
        client = HevyApiClient(api_key=key, session=session)
        return await runner(client)


async def _cmd_sync(config: Config) -> int:
    async def run(client: HevyApiClient) -> int:
        store = CacheStore(config.data_dir)
        result = await sync(client, store, page_size=config.page_size)
        mode = "full backfill" if result.full_backfill else "incremental"
        print(
            f"Sync ({mode}): +{result.added} added, ~{result.updated} updated, "
            f"-{result.deleted} deleted · {len(store.workouts)} workouts cached "
            f"· {result.measurements} measurements · {result.routines} routines"
        )
        for error in result.errors:
            print(f"  warning: {error}", file=sys.stderr)
        return 0

    return await _with_client(config, run)


def _cmd_vault(config: Config) -> int:
    store = CacheStore(config.data_dir)
    if not store.workouts:
        print("Cache is empty - run 'hevy-brain sync' first.", file=sys.stderr)
        return 1
    changed = build_vault(config, store)
    total = sum(changed.values())
    detail = ", ".join(f"{k}: {v}" for k, v in changed.items())
    print(f"Vault updated at {config.vault_root} ({total} changes - {detail})")
    return 0


async def _cmd_full(config: Config) -> int:
    code = await _cmd_sync(config)
    if code != 0:
        return code
    return _cmd_vault(config)


def _load_knowledge(config: Config, topics: list[str] | None = None) -> list:
    """Pull cited claims for the given topics (degrade gracefully).

    A missing or unreadable knowledge layer must never break coaching — the
    coach simply falls back to general-knowledge labelling.
    """
    from .knowledge import Claim, KnowledgeAccessError, KnowledgeBase

    claims: list[Claim] = []
    seen: set[tuple[str, str]] = set()
    try:
        kb = KnowledgeBase(config.knowledge_root)
        for topic in topics if topics is not None else config.knowledge_topics:
            for claim in kb.retrieve(topic=topic).claims:
                key = (claim.source_id, claim.anchor)
                if key not in seen:
                    seen.add(key)
                    claims.append(claim)
    except (KnowledgeAccessError, OSError) as err:
        LOGGER.warning("Knowledge base unavailable: %s", err)
    return claims


def _load_knowledge_for_question(config: Config, question: str) -> tuple[list, str]:
    """Question-driven retrieval down the routing order (degrade gracefully).

    Topics named in the question come first, then the question's significant
    terms as a claims-index / notes-grep pattern. With no match at all, the
    configured base topics are the fallback so the pack is never silently
    empty. Returns (claims, one-line retrieval summary).
    """
    from .coach.ask import question_pattern, question_terms
    from .knowledge import Claim, KnowledgeAccessError, KnowledgeBase

    claims: list[Claim] = []
    seen: set[tuple[str, str]] = set()
    parts: list[str] = []

    def _add(batch: Sequence[Claim]) -> int:
        added = 0
        for claim in batch:
            key = (claim.source_id, claim.anchor)
            if key not in seen:
                seen.add(key)
                claims.append(claim)
                added += 1
        return added

    try:
        kb = KnowledgeBase(config.knowledge_root)
        question_lower = question.lower()
        matched = [
            topic
            for topic in kb.available_topics()
            if topic.lower() in question_lower
            and _add(kb.retrieve(topic=topic).claims)
        ]
        if matched:
            parts.append("topics: " + ", ".join(matched))
        pattern = question_pattern(question_terms(question))
        if pattern:
            result = kb.retrieve(pattern=pattern)
            added = _add(result.claims)
            if added:
                parts.append(f"pattern via {result.step} (+{added})")
        if not claims:
            fallback = [
                topic
                for topic in config.knowledge_topics
                if _add(kb.retrieve(topic=topic).claims)
            ]
            if fallback:
                parts.append(
                    "no question match — fallback topics: " + ", ".join(fallback)
                )
    except (KnowledgeAccessError, OSError) as err:
        LOGGER.warning("Knowledge base unavailable: %s", err)
        parts.append("retrieval aborted early — pack may be partial")
    summary = " · ".join(parts) if parts else "corpus gap — no claims matched"
    return claims, f"{summary} · {len(claims)} claims"


def _cmd_ask(config: Config, question: str) -> int:
    from .analytics.prs import exercise_histories
    from .coach import advisor, ask
    from .models import build_records

    question = question.strip()
    if not question:
        print('Provide a question, e.g. hevy-brain ask "..."', file=sys.stderr)
        return 1
    store = CacheStore(config.data_dir)
    if not store.workouts:
        print("Cache is empty - run 'hevy-brain sync' first.", file=sys.stderr)
        return 1
    today = datetime.now(tz=UTC).date()
    records = build_records(store.workouts)
    histories = exercise_histories(records)
    knowledge, retrieval = _load_knowledge_for_question(config, question)
    context = advisor.build_context(
        records,
        histories,
        today,
        templates=store.exercise_templates,
        overrides=config.muscle_overrides,
        plateau_weeks=config.plateau_weeks,
        knowledge=knowledge,
    )
    writer = VaultWriter(config.vault_root)
    config.vault_root.mkdir(parents=True, exist_ok=True)
    note_path = ask.ask_note_path(today, question)
    writer.write(
        note_path,
        ask.render_ask_briefing(question, context, today, retrieval=retrieval),
    )
    print(f"Ask briefing written: {config.vault_root / note_path}")
    print(f"Knowledge bridge: {retrieval}.")
    print(
        "Open it in Claude Code (or paste into claude.ai) and ask Claude to "
        "act as the coach and answer the question - no API key, no per-call cost."
    )
    return 0


def _cmd_coach(config: Config, *, use_api: bool) -> int:
    from .analytics.prs import exercise_histories
    from .coach import advisor, memory
    from .models import build_records

    store = CacheStore(config.data_dir)
    if not store.workouts:
        print("Cache is empty - run 'hevy-brain sync' first.", file=sys.stderr)
        return 1
    today = datetime.now(tz=UTC).date()
    records = build_records(store.workouts)
    histories = exercise_histories(records)
    knowledge = _load_knowledge(config)
    context = advisor.build_context(
        records,
        histories,
        today,
        templates=store.exercise_templates,
        overrides=config.muscle_overrides,
        plateau_weeks=config.plateau_weeks,
        knowledge=knowledge,
    )
    writer = VaultWriter(config.vault_root)
    config.vault_root.mkdir(parents=True, exist_ok=True)

    # Coach memory: grade the prior run's objective focus against newer data,
    # then capture this run's focus for next time. Grade BEFORE recording so we
    # compare against the previous snapshot, not this one. The recap is a
    # non-essential extra — never let it break the core briefing (the scheduled
    # coach runs unattended), so degrade to no-recap on any unexpected error.
    try:
        recap = memory.grade_focus(
            memory.latest_focus(store.meta),
            records,
            histories,
            today,
            plateau_weeks=config.plateau_weeks,
            templates=store.exercise_templates,
            overrides=config.muscle_overrides,
        )
    except Exception:  # noqa: BLE001 - recap is best-effort, must not break coach
        recap = None

    def _save_focus(path: str) -> None:
        memory.record_focus(
            store.meta,
            memory.build_focus_snapshot(
                records,
                histories,
                today,
                path=path,
                plateau_weeks=config.plateau_weeks,
                templates=store.exercise_templates,
                overrides=config.muscle_overrides,
            ),
        )
        store.save()

    claim_note = (
        f"{len(knowledge)} cited claims loaded"
        if knowledge
        else "no cited claims (corpus gap — advice labelled general-knowledge)"
    )

    if not use_api:
        # Default: free briefing analyzed via your Claude subscription.
        note_path = advisor.briefing_note_path(today)
        writer.write(note_path, advisor.render_briefing(context, today, recap=recap))
        _save_focus("free")
        print(f"Free coaching briefing written: {config.vault_root / note_path}")
        print(f"Knowledge bridge: {claim_note}.")
        if recap:
            print("Included a 'since your last briefing' recap from coach memory.")
        print(
            "Open it in Claude Code (or paste into claude.ai) and ask Claude to "
            "act as the coach and analyze it - no API key, no per-call cost."
        )
        return 0

    # Opt-in metered path (requires a billed ANTHROPIC_API_KEY).
    if not config.anthropic_api_key:
        print("ANTHROPIC_API_KEY is not set (required for --api).", file=sys.stderr)
        return 2
    try:
        advisor.check_budget(store.meta, today, config.coach_max_calls_per_day)
        report = advisor.generate_report(context, model=config.coach_model)
        advisor.record_call(store.meta)
        _save_focus("api")
    except advisor.CoachError as err:
        print(f"Coach failed: {err}", file=sys.stderr)
        return 1
    note_path = advisor.coach_note_path(today)
    writer.write(note_path, advisor.render_coach_note(report, today, recap=recap))
    print(f"Coach note written: {config.vault_root / note_path}")
    print(f"Knowledge bridge: {claim_note}.")
    print(f"\n{report.summary}")
    for finding in report.findings:
        print(f"- [{finding.category}] {finding.title}")
    return 0


def _cmd_guide_return(config: Config) -> int:
    from .analytics.comeback import lapse_status, pre_lapse_baselines
    from .analytics.prs import exercise_histories
    from .coach import comeback
    from .models import build_records
    from .vault.drafts import generate_return_drafts

    store = CacheStore(config.data_dir)
    if not store.workouts:
        print("Cache is empty - run 'hevy-brain sync' first.", file=sys.stderr)
        return 1
    today = datetime.now(tz=UTC).date()
    records = build_records(store.workouts)
    lapse = lapse_status(records, today)
    if lapse is None:
        print("No dated workouts in the cache.", file=sys.stderr)
        return 1
    if lapse["days_since"] < config.guide_lapse_days:
        print(
            f"No lapse detected: last workout was {lapse['days_since']} days ago "
            f"(threshold {config.guide_lapse_days} — [guide] lapse_days)."
        )
        return 0

    histories = exercise_histories(records)
    baselines = pre_lapse_baselines(
        records,
        histories,
        weeks=config.guide_baseline_weeks,
        templates=store.exercise_templates,
        overrides=config.muscle_overrides,
    )

    writer = VaultWriter(config.vault_root)
    config.vault_root.mkdir(parents=True, exist_ok=True)
    written, skipped = generate_return_drafts(
        writer,
        store.routines,
        baselines["workout_titles"],
        fraction=config.guide_load_fraction,
        limit=config.guide_draft_limit,
    )

    topics = list(dict.fromkeys([*config.knowledge_topics, "training", "sleep"]))
    knowledge = _load_knowledge(config, topics)
    context = comeback.build_return_context(
        lapse,
        baselines,
        today=today,
        load_fraction=config.guide_load_fraction,
        draft_paths=[*written, *skipped],
        knowledge=knowledge,
    )
    note_path = comeback.return_briefing_path(today)
    writer.write(note_path, comeback.render_return_briefing(context, today))

    print(
        f"Lapse: {lapse['days_since']} days since "
        f"{lapse['last_workout_date'].isoformat()}."
    )
    print(f"Return briefing written: {config.vault_root / note_path}")
    claim_note = (
        f"{len(knowledge)} cited claims loaded"
        if knowledge
        else "no cited claims (corpus gap — advice labelled general-knowledge)"
    )
    print(f"Knowledge bridge: {claim_note}.")
    for path in written:
        print(f"Draft written: {config.vault_root / path}")
    for path in skipped:
        print(f"Draft already exists (kept your copy): {config.vault_root / path}")
    print(
        "Open the briefing in Claude Code and ask Claude to write the comeback "
        "protocol; push a draft with "
        "'hevy-brain push routine <file> --dry-run' when ready."
    )
    return 0


def _cmd_guide_redesign(config: Config) -> int:
    from .analytics.prs import exercise_histories
    from .analytics.redesign import training_snapshot
    from .coach import redesign
    from .models import build_records
    from .vault.drafts import generate_redesign_drafts

    store = CacheStore(config.data_dir)
    if not store.workouts:
        print("Cache is empty - run 'hevy-brain sync' first.", file=sys.stderr)
        return 1
    today = datetime.now(tz=UTC).date()
    records = build_records(store.workouts)
    histories = exercise_histories(records)
    snapshot = training_snapshot(
        records,
        histories,
        weeks=config.guide_redesign_weeks,
        templates=store.exercise_templates,
        overrides=config.muscle_overrides,
        plateau_weeks=config.plateau_weeks,
        push_pull_low=config.push_pull_low,
        push_pull_high=config.push_pull_high,
    )
    if snapshot is None:
        print("No dated workouts in the cache.", file=sys.stderr)
        return 1

    writer = VaultWriter(config.vault_root)
    config.vault_root.mkdir(parents=True, exist_ok=True)
    written, skipped = generate_redesign_drafts(
        writer,
        store.routines,
        snapshot["workout_titles"],
        limit=config.guide_draft_limit,
    )

    knowledge, retrieval = _load_knowledge_for_question(
        config, redesign.REDESIGN_QUERY
    )
    available = sorted(histories)
    if store.exercise_templates:
        available = sorted(
            set(available)
            | {t.get("title") or "" for t in store.exercise_templates.values()}
            - {""}
        )
    context = redesign.build_redesign_context(
        snapshot,
        today=today,
        draft_paths=[*written, *skipped],
        available=available,
        knowledge=knowledge,
    )
    note_path = redesign.redesign_briefing_path(today)
    writer.write(
        note_path,
        redesign.render_redesign_briefing(context, today, retrieval=retrieval),
    )

    print(
        f"Snapshot: {snapshot['sessions']} sessions over "
        f"{snapshot['weeks']} weeks ending "
        f"{snapshot['window_end'].isoformat()} "
        f"({len(snapshot['plateaus'])} plateaus, push/pull "
        f"{snapshot['push_pull_flag'] or 'n/a'})."
    )
    print(f"Redesign briefing written: {config.vault_root / note_path}")
    print(f"Knowledge bridge: {retrieval}.")
    for path in written:
        print(f"Draft written: {config.vault_root / path}")
    for path in skipped:
        print(f"Draft already exists (kept your copy): {config.vault_root / path}")
    print(
        "Open the briefing in Claude Code and ask Claude to redesign the "
        "programme; apply it by editing a draft's frontmatter, then "
        "'hevy-brain push routine <file> --dry-run'."
    )
    return 0


async def _cmd_push_workout(
    config: Config, file: Path, *, update: bool = False, dry_run: bool = False
) -> int:
    if update:
        return await _cmd_push_workout_update(config, file, dry_run=dry_run)
    if dry_run:
        print(
            "--dry-run only applies to 'push workout --update'.", file=sys.stderr
        )
        return 1

    from .writeback.hevy_push import (
        PlannedWorkoutError,
        parse_planned_workout,
        push_workout,
    )

    try:
        body = parse_planned_workout(file)
    except (PlannedWorkoutError, OSError) as err:
        print(f"Cannot parse planned workout: {err}", file=sys.stderr)
        return 1

    workout = body["workout"]
    sets = sum(len(e["sets"]) for e in workout["exercises"])
    print(
        f"Pushing workout '{workout['title']}' "
        f"({len(workout['exercises'])} exercises, {sets} sets) to Hevy..."
    )

    async def run(client: HevyApiClient) -> int:
        await push_workout(client, body)
        print("Workout created in Hevy. Run 'hevy-brain full' to pull it back.")
        return 0

    return await _with_client(config, run)


async def _cmd_push_workout_update(
    config: Config, file: Path, *, dry_run: bool
) -> int:
    from .api.client import HevyApiClientError
    from .writeback.hevy_push import (
        WorkoutNoteError,
        parse_workout_note,
        push_workout_update,
        unwrap_workout,
        workout_diff,
    )

    try:
        workout_id, body = parse_workout_note(file)
    except (WorkoutNoteError, OSError) as err:
        print(f"Cannot parse workout note: {err}", file=sys.stderr)
        return 1

    async def run(client: HevyApiClient) -> int:
        try:
            current = unwrap_workout(await client.async_get_workout(workout_id))
        except HevyApiClientError as err:
            print(f"Cannot fetch workout {workout_id}: {err}", file=sys.stderr)
            return 1
        if current is None:
            print(f"Workout {workout_id} not found in Hevy.", file=sys.stderr)
            return 1

        diff = workout_diff(current, body)
        title = body["workout"]["title"]
        if not diff:
            print(f"Workout '{title}': no changes — nothing to push.")
            return 0
        print(f"Workout '{title}' ({workout_id}) — changes to push:")
        for line in diff:
            print(f"  {line}")
        if dry_run:
            print("Dry run — nothing sent.")
            return 0
        try:
            await push_workout_update(client, workout_id, body)
        except HevyApiClientError as err:
            print(f"Push failed: {err}", file=sys.stderr)
            return 1
        print(
            "Workout updated in Hevy (full replacement). "
            "Run 'hevy-brain full' to refresh the vault."
        )
        return 0

    return await _with_client(config, run)


async def _cmd_push_routine(config: Config, file: Path, *, dry_run: bool) -> int:
    from .api.client import HevyApiClientError
    from .writeback.hevy_push import (
        RoutineNoteError,
        parse_routine_note,
        push_routine,
        routine_diff,
        unwrap_routine,
    )

    try:
        routine_id, body = parse_routine_note(file)
    except (RoutineNoteError, OSError) as err:
        print(f"Cannot parse routine note: {err}", file=sys.stderr)
        return 1

    async def run(client: HevyApiClient) -> int:
        try:
            current = unwrap_routine(await client.async_get_routine(routine_id))
        except HevyApiClientError as err:
            print(f"Cannot fetch routine {routine_id}: {err}", file=sys.stderr)
            return 1
        if current is None:
            print(f"Routine {routine_id} not found in Hevy.", file=sys.stderr)
            return 1

        diff = routine_diff(current, body)
        title = body["routine"]["title"]
        if not diff:
            print(f"Routine '{title}': no changes — nothing to push.")
            return 0
        print(f"Routine '{title}' ({routine_id}) — changes to push:")
        for line in diff:
            print(f"  {line}")
        if dry_run:
            print("Dry run — nothing sent.")
            return 0
        try:
            await push_routine(client, routine_id, body)
        except HevyApiClientError as err:
            print(f"Push failed: {err}", file=sys.stderr)
            return 1
        print(
            "Routine updated in Hevy (full replacement). "
            "Run 'hevy-brain full' to refresh the vault."
        )
        return 0

    return await _with_client(config, run)


async def _cmd_push_measurement(config: Config, args: argparse.Namespace) -> int:
    from .writeback.hevy_push import MEASUREMENT_FIELDS, push_measurement

    fields = {
        name: getattr(args, name)
        for name in MEASUREMENT_FIELDS
        if getattr(args, name, None) is not None
    }
    if not fields:
        print(
            "Provide at least one measurement (e.g. --weight-kg 78.4).",
            file=sys.stderr,
        )
        return 1

    async def run(client: HevyApiClient) -> int:
        date_str = await push_measurement(client, fields, args.date)
        printable = ", ".join(f"{k}={v:g}" for k, v in fields.items())
        print(f"Measurement logged for {date_str}: {printable}")
        return 0

    return await _with_client(config, run)


def _cmd_status(config: Config) -> int:
    store = CacheStore(config.data_dir)
    meta = store.meta
    print(f"Cache: {config.data_dir}")
    print(f"  workouts: {len(store.workouts)} (archived: {len(store.archived)})")
    print(f"  measurements: {len(store.measurements)}")
    print(f"  exercise templates: {len(store.exercise_templates)}")
    print(
        f"  routines: {len(store.routines)} "
        f"(archived: {len(store.archived_routines)})"
    )
    print(f"  last sync: {meta.get('last_sync', 'never')}")
    print(f"  events cursor: {meta.get('events_cursor', 'none')}")
    print(f"Vault: {config.vault_root}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="hevy-brain",
        description=(
            "Sync Hevy workouts into an Obsidian second brain, analyze "
            "training patterns, and push changes back to Hevy."
        ),
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync", help="Fetch new/changed data from Hevy into the cache")
    sub.add_parser("vault", help="Regenerate all Obsidian notes from the cache")
    sub.add_parser("full", help="sync + vault in one go")
    coach = sub.add_parser(
        "coach",
        help="Write a free coaching briefing (analyze it with your Claude sub)",
    )
    coach.add_argument(
        "--api",
        action="store_true",
        help="Use the metered Anthropic API instead (needs ANTHROPIC_API_KEY)",
    )
    sub.add_parser("status", help="Show cache and config status")

    ask = sub.add_parser(
        "ask",
        help="Answer one specific question, grounded in your data + cited claims",
    )
    ask.add_argument(
        "question",
        help='The question, quoted (e.g. "How do I get my bench moving again?")',
    )

    guide = sub.add_parser(
        "guide", help="Scenario guidance grounded in your data + cited claims"
    )
    guide_sub = guide.add_subparsers(dest="guide_command", required=True)
    guide_sub.add_parser(
        "return",
        help=(
            "Comeback protocol after a training lapse: baselines, briefing, "
            "and Return Week 1 routine drafts"
        ),
    )
    guide_sub.add_parser(
        "redesign",
        help=(
            "Programme change: current split/volume/plateau snapshot, "
            "briefing, and editable Redesign routine drafts"
        ),
    )

    push = sub.add_parser("push", help="Write data TO Hevy (always manual)")
    push_sub = push.add_subparsers(dest="push_command", required=True)

    push_workout = push_sub.add_parser(
        "workout",
        help="Create a workout from a planned note, or fix a logged one (--update)",
    )
    push_workout.add_argument(
        "file",
        type=Path,
        help="Planned-workout note (create) or workout note (--update)",
    )
    push_workout.add_argument(
        "--update",
        action="store_true",
        help="Update the logged workout named by the note's hevy_id "
        "(PUT, full replacement) instead of creating a new one",
    )
    push_workout.add_argument(
        "--dry-run",
        action="store_true",
        help="With --update: show the diff against Hevy and stop — send nothing",
    )

    push_routine = push_sub.add_parser(
        "routine",
        help="Update a routine in Hevy from a routine note (PUT, full replacement)",
    )
    push_routine.add_argument("file", type=Path, help="Routine .md file (or draft)")
    push_routine.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the diff against Hevy and stop — send nothing",
    )

    push_measurement = push_sub.add_parser(
        "measurement", help="Log a body measurement in Hevy"
    )
    push_measurement.add_argument(
        "--date", default=None, help="YYYY-MM-DD (default today)"
    )
    from .writeback.hevy_push import MEASUREMENT_FIELDS

    for name in MEASUREMENT_FIELDS:
        push_measurement.add_argument(
            f"--{name.replace('_', '-')}", dest=name, type=float, default=None
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _configure_output()
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(config_file=args.config)

    if args.command == "sync":
        return asyncio.run(_cmd_sync(config))
    if args.command == "vault":
        return _cmd_vault(config)
    if args.command == "full":
        return asyncio.run(_cmd_full(config))
    if args.command == "coach":
        return _cmd_coach(config, use_api=args.api)
    if args.command == "ask":
        return _cmd_ask(config, args.question)
    if args.command == "status":
        return _cmd_status(config)
    if args.command == "guide":
        if args.guide_command == "return":
            return _cmd_guide_return(config)
        if args.guide_command == "redesign":
            return _cmd_guide_redesign(config)
        return 1
    if args.command == "push":
        if args.push_command == "workout":
            return asyncio.run(
                _cmd_push_workout(
                    config, args.file, update=args.update, dry_run=args.dry_run
                )
            )
        if args.push_command == "routine":
            return asyncio.run(
                _cmd_push_routine(config, args.file, dry_run=args.dry_run)
            )
        return asyncio.run(_cmd_push_measurement(config, args))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
