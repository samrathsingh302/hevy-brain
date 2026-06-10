"""Tests for write-back to Hevy."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from hevy_brain.api.client import HevyApiClientConflictError
from hevy_brain.writeback.hevy_push import (
    PlannedWorkoutError,
    parse_planned_workout,
    push_measurement,
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
