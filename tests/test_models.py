"""Record building: Hevy UTC payloads become Europe/London-dated records.

These guard the deferred half of the London fix — dating and displaying a
workout by its London wall-clock, not the UTC calendar day, from start_time.
"""

from __future__ import annotations

from datetime import date

from hevy_brain.clock import LONDON
from hevy_brain.models import build_records, build_workout_record
from hevy_brain.vault.workouts import render_workout_note, workout_note_paths


def _raw(workout_id: str, start: str | None, end: str | None, title: str = "Session"):
    return {
        "id": workout_id,
        "title": title,
        "start_time": start,
        "end_time": end,
        "exercises": [],
    }


def test_bst_after_midnight_workout_dates_to_london_day() -> None:
    # 23:30 UTC on 1 July == 00:30 BST on the 2nd. A naive UTC .date() would
    # file this on the 1st; the record must carry the London day.
    record = build_workout_record(
        _raw("w1", "2026-07-01T23:30:00+00:00", "2026-07-02T00:30:00+00:00")
    )
    assert record["start_time"].tzinfo is LONDON
    assert record["start_time"].date() == date(2026, 7, 2)
    assert (record["start_time"].hour, record["start_time"].minute) == (0, 30)
    assert record["end_time"].date() == date(2026, 7, 2)
    # The instant is unchanged, so duration survives the conversion.
    assert record["duration_seconds"] == 3600.0


def test_bst_evening_workout_reads_in_local_hours() -> None:
    # 21:18 UTC in April == 22:18 BST: same civil day, local clock.
    record = build_workout_record(
        _raw("w2", "2026-04-11T21:18:59+00:00", "2026-04-11T22:00:00+00:00")
    )
    assert record["start_time"].date() == date(2026, 4, 11)
    assert (record["start_time"].hour, record["start_time"].minute) == (22, 18)


def test_gmt_winter_workout_matches_utc() -> None:
    record = build_workout_record(
        _raw("w3", "2026-01-15T17:00:00+00:00", "2026-01-15T18:00:00+00:00")
    )
    assert record["start_time"].date() == date(2026, 1, 15)
    assert record["start_time"].hour == 17  # GMT == UTC


def test_note_filename_and_header_use_london_day() -> None:
    record = build_workout_record(
        _raw("w1", "2026-07-01T23:30:00+00:00", "2026-07-02T00:30:00+00:00", "Late")
    )
    assert workout_note_paths([record])["w1"] == "Workouts/2026-07-02 Late.md"
    note = render_workout_note(record, [])
    assert "02 July 2026 00:30" in note  # local date + time in the header
    assert "2026-07-02" in note  # frontmatter date / start_time


def test_records_without_start_time_are_dropped() -> None:
    records = build_records(
        {
            "good": _raw(
                "good", "2026-07-01T17:00:00+00:00", "2026-07-01T18:00:00+00:00"
            ),
            "bad": _raw("bad", None, None),
        }
    )
    assert [r["id"] for r in records] == ["good"]
