"""Tests for write-back to Hevy."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import make_routine, make_routine_exercise, make_routine_set

from hevy_brain.api.client import HevyApiClientConflictError
from hevy_brain.vault.routines import render_routine_note
from hevy_brain.writeback.hevy_push import (
    PlannedWorkoutError,
    RoutineNoteError,
    parse_planned_workout,
    parse_routine_note,
    push_measurement,
    routine_diff,
    unwrap_routine,
)

PLANNED = """\
---
type: hevy-planned-workout
title: Coach Push Day
description: Suggested by coach
start_time: 2026-06-11T17:00:00+00:00
end_time: 2026-06-11T18:00:00+00:00
exercises:
  - name: Bench Press (Barbell)
    exercise_template_id: T-BENCH
    sets:
      - { weight_kg: 60, reps: 8 }
      - { weight_kg: 60, reps: 8, type: failure }
  - template_id: T-LAT
    notes: slow eccentric
    sets:
      - { weight_kg: 10, reps: 12 }
---

# Coach Push Day
Free-form notes here are ignored by the parser.
"""


def test_parse_planned_workout(tmp_path: Path) -> None:
    file = tmp_path / "plan.md"
    file.write_text(PLANNED, encoding="utf-8")

    body = parse_planned_workout(file)

    workout = body["workout"]
    assert workout["title"] == "Coach Push Day"
    assert workout["description"] == "Suggested by coach"
    assert workout["start_time"] == "2026-06-11T17:00:00+00:00"
    assert len(workout["exercises"]) == 2
    bench = workout["exercises"][0]
    assert bench["exercise_template_id"] == "T-BENCH"
    assert bench["sets"][1]["type"] == "failure"
    lat = workout["exercises"][1]
    assert lat["exercise_template_id"] == "T-LAT"
    assert lat["notes"] == "slow eccentric"


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("type: something-else", "type"),
        ("title: Coach Push Day\n", "title"),
    ],
)
def test_parse_rejects_bad_notes(tmp_path: Path, mutation: str, match: str) -> None:
    if mutation.startswith("type:"):
        text = PLANNED.replace("type: hevy-planned-workout", mutation)
    else:
        text = PLANNED.replace("title: Coach Push Day\n", "")
    file = tmp_path / "plan.md"
    file.write_text(text, encoding="utf-8")

    with pytest.raises(PlannedWorkoutError, match=match):
        parse_planned_workout(file)


def test_parse_requires_sets(tmp_path: Path) -> None:
    text = PLANNED.replace(
        "  - template_id: T-LAT\n    notes: slow eccentric\n    sets:\n      - { weight_kg: 10, reps: 12 }\n",
        "  - template_id: T-LAT\n    sets: []\n",
    )
    file = tmp_path / "plan.md"
    file.write_text(text, encoding="utf-8")

    with pytest.raises(PlannedWorkoutError, match="sets"):
        parse_planned_workout(file)


ROUTINE_NOTE = """\
---
type: hevy-routine
hevy_routine_id: r1
title: Push Day A
notes: focus on tempo
exercises:
  - name: Bench Press (Barbell)
    exercise_template_id: T-BENCH
    rest_seconds: 120
    sets:
      - { weight_kg: 60, reps: 8 }
      - { weight_kg: 65, type: failure, rep_range: { start: 5, end: 8 } }
  - exercise_template_id: T-LAT
    notes: slow eccentric
    sets:
      - { weight_kg: 10, reps: 12 }
---

# Push Day A
Anything below the frontmatter is ignored by the parser.
"""


def test_parse_routine_note(tmp_path: Path) -> None:
    file = tmp_path / "routine.md"
    file.write_text(ROUTINE_NOTE, encoding="utf-8")

    routine_id, body = parse_routine_note(file)

    assert routine_id == "r1"
    routine = body["routine"]
    assert routine["title"] == "Push Day A"
    assert routine["notes"] == "focus on tempo"
    bench = routine["exercises"][0]
    assert bench["exercise_template_id"] == "T-BENCH"
    assert bench["rest_seconds"] == 120
    assert bench["sets"][1]["type"] == "failure"
    assert bench["sets"][1]["rep_range"] == {"start": 5, "end": 8}
    assert routine["exercises"][1]["notes"] == "slow eccentric"


def test_parse_routine_note_accepts_half_open_rep_range(tmp_path: Path) -> None:
    """The live account has a set with rep_range {start: 8, end: null} ("8+
    reps" in Hevy). Full-replacement fidelity: parse it and keep the null
    end exactly as the API returned it (found live 13/06/2026 — the old
    parser rejected the routine's own unedited note)."""
    file = tmp_path / "routine.md"
    file.write_text(
        ROUTINE_NOTE.replace(
            "rep_range: { start: 5, end: 8 }",
            "rep_range: { start: 5, end: null }",
        ),
        encoding="utf-8",
    )

    _, body = parse_routine_note(file)

    sets = body["routine"]["exercises"][0]["sets"]
    assert sets[1]["rep_range"] == {"start": 5, "end": None}


def test_parse_routine_note_omits_empty_notes(tmp_path: Path) -> None:
    """Hevy 400s on "notes": "" — a note without routine notes must omit the
    key entirely (verified live 13/06/2026: omission = no notes in Hevy)."""
    file = tmp_path / "routine.md"
    file.write_text(
        ROUTINE_NOTE.replace("notes: focus on tempo\n", ""), encoding="utf-8"
    )

    _, body = parse_routine_note(file)

    assert "notes" not in body["routine"]


@pytest.mark.parametrize(
    ("needle", "replacement", "match"),
    [
        ("type: hevy-routine", "type: something-else", "type"),
        ("hevy_routine_id: r1\n", "", "hevy_routine_id"),
        ("title: Push Day A\n", "", "title"),
        ("reps: 12", "reps: 12, rpe: 8", "RPE"),
        ("rep_range: { start: 5, end: 8 }", "rep_range: { end: 8 }", "rep_range"),
    ],
)
def test_parse_routine_note_rejects_bad_notes(
    tmp_path: Path, needle: str, replacement: str, match: str
) -> None:
    file = tmp_path / "routine.md"
    file.write_text(ROUTINE_NOTE.replace(needle, replacement), encoding="utf-8")

    with pytest.raises(RoutineNoteError, match=match):
        parse_routine_note(file)


def test_unedited_managed_note_diffs_clean(tmp_path: Path) -> None:
    """A vault-rendered note parsed straight back must diff empty against the
    routine it was rendered from — the round-trip guarantee."""
    routine = make_routine(
        "r1",
        exercises=[
            make_routine_exercise(
                sets=[
                    make_routine_set(60, 8),
                    make_routine_set(65, None, rep_range={"start": 5, "end": 8}),
                ]
            )
        ],
    )
    file = tmp_path / "note.md"
    file.write_text(render_routine_note(routine, "PPL"), encoding="utf-8")

    routine_id, body = parse_routine_note(file)

    assert routine_id == "r1"
    assert routine_diff(routine, body) == []


def test_routine_diff_reports_changes(tmp_path: Path) -> None:
    routine = make_routine(
        "r1",
        exercises=[
            make_routine_exercise(sets=[make_routine_set(60, 8)]),
            make_routine_exercise("Lateral Raise (Dumbbell)", "T-LAT", index=1),
        ],
    )
    file = tmp_path / "note.md"
    file.write_text(render_routine_note(routine, None), encoding="utf-8")
    text = file.read_text(encoding="utf-8")
    text = text.replace("title: Push Day A", "title: Push Day B")
    text = text.replace("weight_kg: 60", "weight_kg: 65")
    # Drop the second exercise from the frontmatter spec entirely.
    start = text.index("- name: Lateral Raise (Dumbbell)")
    end = text.index("tags:")
    file.write_text(text[:start] + text[end:], encoding="utf-8")

    _, body = parse_routine_note(file)
    diff = routine_diff(routine, body)

    assert any("title" in line for line in diff)
    assert any("60kg" in line and "65kg" in line for line in diff)
    assert any(line.startswith("−") for line in diff)


def test_unwrap_routine_handles_wrapper_shapes() -> None:
    assert unwrap_routine({"routine": {"id": "r1"}}) == {"id": "r1"}
    assert unwrap_routine({"routine": [{"id": "r1"}]}) == {"id": "r1"}
    assert unwrap_routine({"id": "r1"}) == {"id": "r1"}
    assert unwrap_routine({"routine": []}) is None
    assert unwrap_routine(None) is None


async def test_cmd_push_routine_dry_run_sends_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hevy_brain import cli

    routine = make_routine("r1")
    file = tmp_path / "note.md"
    text = render_routine_note(routine, None).replace("weight_kg: 60", "weight_kg: 70")
    file.write_text(text, encoding="utf-8")

    client = MagicMock()
    client.async_get_routine = AsyncMock(return_value={"routine": routine})
    client.async_update_routine = AsyncMock(return_value={})

    async def fake_with_client(config, runner):
        return await runner(client)

    monkeypatch.setattr(cli, "_with_client", fake_with_client)

    assert await cli._cmd_push_routine(MagicMock(), file, dry_run=True) == 0
    client.async_update_routine.assert_not_awaited()

    assert await cli._cmd_push_routine(MagicMock(), file, dry_run=False) == 0
    client.async_update_routine.assert_awaited_once()
    routine_id, body = client.async_update_routine.await_args.args
    assert routine_id == "r1"
    assert body["routine"]["exercises"][0]["sets"][0]["weight_kg"] == 70


async def test_cmd_push_routine_skips_put_when_no_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hevy_brain import cli

    routine = make_routine("r1")
    file = tmp_path / "note.md"
    file.write_text(render_routine_note(routine, None), encoding="utf-8")

    client = MagicMock()
    client.async_get_routine = AsyncMock(return_value={"routine": routine})
    client.async_update_routine = AsyncMock(return_value={})

    async def fake_with_client(config, runner):
        return await runner(client)

    monkeypatch.setattr(cli, "_with_client", fake_with_client)

    assert await cli._cmd_push_routine(MagicMock(), file, dry_run=False) == 0
    client.async_update_routine.assert_not_awaited()


async def test_push_measurement_posts() -> None:
    client = MagicMock()
    client.async_create_body_measurement = AsyncMock(return_value={})

    date_str = await push_measurement(
        client, {"weight_kg": 78.4}, date_str="2026-06-10"
    )

    assert date_str == "2026-06-10"
    body = client.async_create_body_measurement.await_args.args[0]
    assert body == {"weight_kg": 78.4, "date": "2026-06-10"}


async def test_push_measurement_falls_back_to_put_on_conflict() -> None:
    client = MagicMock()
    client.async_create_body_measurement = AsyncMock(
        side_effect=HevyApiClientConflictError("exists")
    )
    client.async_update_body_measurement = AsyncMock(return_value={})

    await push_measurement(client, {"weight_kg": 78.4}, date_str="2026-06-10")

    args = client.async_update_body_measurement.await_args.args
    assert args[0] == "2026-06-10"
    assert args[1] == {"weight_kg": 78.4}


async def test_push_measurement_validates_fields() -> None:
    client = MagicMock()
    with pytest.raises(ValueError, match="Unknown"):
        await push_measurement(client, {"bogus": 1.0})
    with pytest.raises(ValueError, match="At least one"):
        await push_measurement(client, {})
