"""Tests for guide redesign: snapshot, drafts, briefing, and the CLI (E2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from conftest import (
    make_exercise,
    make_routine,
    make_routine_exercise,
    make_routine_set,
    make_set,
    make_workout,
)

from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.analytics.redesign import (
    classify_push_pull,
    split_summary,
    training_snapshot,
    weekly_sets_by_group,
)
from hevy_brain.coach import redesign
from hevy_brain.knowledge import Claim
from hevy_brain.models import build_records
from hevy_brain.vault.drafts import (
    generate_redesign_drafts,
    render_redesign_draft,
)
from hevy_brain.vault.writer import VaultWriter
from hevy_brain.writeback.hevy_push import parse_routine_note, routine_diff

# Months after the fixture workouts (which end 2026-06-08): the snapshot must
# describe the programme as last run, not collapse because of the lapse.
TODAY = date(2026, 8, 10)


def _claims() -> list[Claim]:
    return [
        Claim(
            source_id="xJ0IBzCjEPk",
            anchor="claim-07",
            text="Persistent elevated resting heart rate signals overtraining.",
            evidence="strong",
            claim_type="INFO",
        )
    ]


def _snapshot(raw_workouts: dict, **kwargs):
    records = build_records(raw_workouts)
    histories = exercise_histories(records)
    return training_snapshot(records, histories, **kwargs)


# -- analytics: split ------------------------------------------------------


def test_split_summary_groups_sessions_by_title(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)

    split = split_summary(records)

    assert [e["title"] for e in split] == ["Push Day", "Pull Day"]
    push = split[0]
    assert push["sessions"] == 2
    # Bench volume dwarfs lateral raises: chest ranks first.
    assert push["groups"][0] == "chest"
    assert split[1]["groups"][0] == "back"


def test_weekly_sets_by_group_averages_over_weeks(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)

    sets = weekly_sets_by_group(records, weeks=2)

    # 4 bench sets + 1 lateral-raise set + 2 pull sets over 2 weeks.
    assert sets["chest"] == 2.0
    assert sets["back"] == 1.0
    assert sets["shoulders"] == 0.5


def test_weekly_sets_by_group_excludes_warmups() -> None:
    workout = make_workout(
        "w1",
        "Push Day",
        exercises=[
            make_exercise(
                sets=[
                    make_set(40, 10, type="warmup"),
                    make_set(80, 5),
                    make_set(80, 5),
                ]
            )
        ],
    )
    records = build_records({"w1": workout})

    sets = weekly_sets_by_group(records, weeks=1)

    # Working sets only: the redesign's volume targets must not be anchored
    # to a number inflated by warm-ups.
    assert sets == {"chest": 2.0}


def test_classify_push_pull_uses_the_config_band() -> None:
    assert classify_push_pull(None, 0.8, 1.25) is None
    assert classify_push_pull(1.0, 0.8, 1.25) == "balanced"
    assert classify_push_pull(2.0, 0.8, 1.25) == "push-heavy"
    assert classify_push_pull(0.5, 0.8, 1.25) == "pull-heavy"


# -- analytics: snapshot ---------------------------------------------------


def test_training_snapshot_survives_a_lapse(raw_workouts: dict) -> None:
    snapshot = _snapshot(raw_workouts, weeks=4)

    assert snapshot is not None
    # Window anchored at the LAST workout, not today: sessions still counted.
    assert snapshot["window_end"] == date(2026, 6, 8)
    assert snapshot["sessions"] == 3
    assert [e["title"] for e in snapshot["split"]] == ["Push Day", "Pull Day"]
    # History covers 3 of the 4 window weeks: 4 chest sets over 3 weeks.
    assert snapshot["weekly_sets_by_group"]["chest"] == pytest.approx(4 / 3)


def test_training_snapshot_flags_untrained_groups(raw_workouts: dict) -> None:
    snapshot = _snapshot(raw_workouts, weeks=4)

    # Fixtures train chest/shoulders/back only.
    assert "legs" in snapshot["untrained_groups"]
    assert "core" in snapshot["untrained_groups"]
    assert "chest" not in snapshot["untrained_groups"]


def test_training_snapshot_classifies_push_pull(raw_workouts: dict) -> None:
    snapshot = _snapshot(raw_workouts, weeks=4)

    assert snapshot["push_pull_ratio"] is not None
    assert snapshot["push_pull_flag"] in ("push-heavy", "pull-heavy", "balanced")
    # The fixture band is fixed: assert the actual classification too.
    assert snapshot["push_pull_flag"] == classify_push_pull(
        snapshot["push_pull_ratio"], 0.8, 1.25
    )


def test_training_snapshot_detects_window_anchored_plateaus() -> None:
    # 8 weekly bench sessions stuck at the same load, ending 2026-06-08 —
    # months before TODAY. Anchored at today the plateau would vanish.
    from datetime import timedelta

    workouts = {}
    for i in range(8):
        day = date(2026, 6, 8) - timedelta(weeks=i)
        wid = f"w{i}"
        workouts[wid] = make_workout(
            wid,
            "Push Day",
            start=f"{day.isoformat()}T17:00:00+00:00",
            end=f"{day.isoformat()}T18:00:00+00:00",
            exercises=[make_exercise(sets=[make_set(80, 5), make_set(80, 5)])],
        )

    records = build_records(workouts)
    histories = exercise_histories(records)
    snapshot = training_snapshot(records, histories, weeks=8, plateau_weeks=4)

    assert [p["exercise"] for p in snapshot["plateaus"]] == ["Bench Press (Barbell)"]


def test_training_snapshot_empty_records() -> None:
    assert training_snapshot([], {}) is None


def test_training_snapshot_short_history_is_not_diluted(
    raw_workouts: dict,
) -> None:
    # 3 sessions across 3 calendar weeks of history, asked for an 8-week
    # window: weekly rates must average over the covered weeks, not 8.
    snapshot = _snapshot(raw_workouts, weeks=8)

    assert snapshot["effective_weeks"] == 3
    assert snapshot["sessions_per_week"] == pytest.approx(1.0)
    assert snapshot["weekly_sets_by_group"]["chest"] == pytest.approx(4 / 3)


def test_build_redesign_context_states_short_history(raw_workouts: dict) -> None:
    snapshot = _snapshot(raw_workouts, weeks=8)
    context = redesign.build_redesign_context(snapshot, today=TODAY)

    assert "**3 of the 8 window weeks**" in context


# -- drafts ----------------------------------------------------------------


def test_render_redesign_draft_round_trips_unchanged(tmp_path: Path) -> None:
    routine = make_routine(
        "r9",
        "Push Day A",
        exercises=[
            make_routine_exercise(
                sets=[make_routine_set(80, 5), make_routine_set(80, 5)]
            )
        ],
    )

    rel_path, content = render_redesign_draft(routine)

    assert rel_path == "Routines/Drafts/Redesign — Push Day A.md"
    writer = VaultWriter(tmp_path)
    writer.write(rel_path, content)

    # The unedited draft must be an exact copy: same id, same TITLE, same
    # loads — so pushing it before editing is a guaranteed no-op.
    routine_id, body = parse_routine_note(tmp_path / rel_path)
    assert routine_id == "r9"
    assert body["routine"]["title"] == "Push Day A"
    assert body["routine"]["exercises"][0]["sets"][0]["weight_kg"] == 80.0


def test_render_redesign_draft_unedited_push_is_a_no_op(tmp_path: Path) -> None:
    # The invariant that gates the PUT: routine_diff against the source
    # routine must be EMPTY, across every field the spec round-trips —
    # notes, rep ranges (half-open included, as on the live account),
    # supersets, rest, and a set with no type key.
    typeless_set = make_routine_set(60, None, rep_range={"start": 8, "end": 12})
    del typeless_set["type"]
    half_open_set = make_routine_set(17.5, None, rep_range={"start": 8, "end": None})
    routine = make_routine(
        "r9",
        "Push Day A",
        exercises=[
            make_routine_exercise(
                sets=[make_routine_set(80, 5), typeless_set, half_open_set],
                rest_seconds=90,
            ),
            make_routine_exercise(
                "Lateral Raise (Dumbbell)", "T-LAT", index=1, rest_seconds=None
            ),
        ],
    )
    routine["notes"] = "Focus on tempo."
    routine["exercises"][0]["superset_id"] = 1

    rel_path, content = render_redesign_draft(routine)
    writer = VaultWriter(tmp_path)
    writer.write(rel_path, content)
    _, body = parse_routine_note(tmp_path / rel_path)

    assert routine_diff(routine, body) == []


def test_render_redesign_draft_body_warns_and_shows_current(tmp_path: Path) -> None:
    routine = make_routine(
        "r9",
        "Push Day A",
        exercises=[make_routine_exercise(sets=[make_routine_set(80, 5)])],
    )

    _, content = render_redesign_draft(routine)

    assert "80 kg × 5" in content
    assert "replaces" in content
    assert "--dry-run" in content
    assert "unedited sends nothing" in content


def test_render_redesign_draft_preserves_routine_notes(tmp_path: Path) -> None:
    routine = make_routine("r9", "Push Day A")
    routine["notes"] = "Focus on tempo."

    rel_path, content = render_redesign_draft(routine)
    writer = VaultWriter(tmp_path)
    writer.write(rel_path, content)

    # PUT is a full replacement: a draft without the routine's notes would
    # silently wipe them in Hevy on push.
    _, body = parse_routine_note(tmp_path / rel_path)
    assert body["routine"]["notes"] == "Focus on tempo."


def test_generate_redesign_drafts_is_write_once(tmp_path: Path) -> None:
    writer = VaultWriter(tmp_path)
    routines = {"r1": make_routine("r1", "Push Day")}

    written, skipped = generate_redesign_drafts(writer, routines, ["Push Day"])
    assert written == ["Routines/Drafts/Redesign — Push Day.md"]
    assert not skipped

    draft = tmp_path / written[0]
    draft.write_text(draft.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")

    written2, skipped2 = generate_redesign_drafts(writer, routines, ["Push Day"])
    assert not written2
    assert skipped2 == written
    assert "edited" in draft.read_text(encoding="utf-8")


def test_generate_redesign_drafts_suffixes_duplicate_titles(
    tmp_path: Path,
) -> None:
    writer = VaultWriter(tmp_path)
    routines = {
        "ralpha111": make_routine(
            "ralpha111", "Push Day", updated_at="2026-06-09T09:00:00+00:00"
        ),
        "rbeta2222": make_routine(
            "rbeta2222", "Push Day", updated_at="2026-06-01T09:00:00+00:00"
        ),
    }

    written, skipped = generate_redesign_drafts(writer, routines, [])

    assert not skipped
    assert written == [
        "Routines/Drafts/Redesign — Push Day.md",
        "Routines/Drafts/Redesign — Push Day (rbeta222).md",
    ]


# -- briefing --------------------------------------------------------------


def _context(raw_workouts: dict, **kwargs) -> str:
    snapshot = _snapshot(raw_workouts, weeks=4)
    assert snapshot is not None
    return redesign.build_redesign_context(snapshot, today=TODAY, **kwargs)


def test_build_redesign_context_grounds_the_numbers(raw_workouts: dict) -> None:
    context = _context(raw_workouts)

    assert "3 sessions" in context
    assert "Push Day: 2 sessions" in context
    assert "chest: 1.3 sets/week" in context
    assert "Untrained in the window: " in context
    assert "legs" in context
    assert "push/pull ratio" in context


def test_build_redesign_context_flags_stale_window(raw_workouts: dict) -> None:
    context = _context(raw_workouts)

    # TODAY is 63 days after the last fixture workout — the staleness of the
    # snapshot must be stated, not implied.
    assert "**63 days ago**" in context


def test_build_redesign_context_lists_drafts_claims_available(
    raw_workouts: dict,
) -> None:
    context = _context(
        raw_workouts,
        draft_paths=["Routines/Drafts/Redesign — Push Day.md"],
        available=["Bench Press (Barbell)", "Squat (Barbell)"],
        knowledge=_claims(),
    )

    assert "[[Routines/Drafts/Redesign — Push Day.md]]" in context
    assert "--dry-run" in context
    assert "Squat (Barbell)" in context
    assert "[[xJ0IBzCjEPk#^claim-07]]" in context


def test_build_redesign_context_flags_empty_corpus(raw_workouts: dict) -> None:
    context = _context(raw_workouts, knowledge=[])

    assert "No cited claims" in context


def test_render_redesign_briefing_is_self_contained(raw_workouts: dict) -> None:
    note = redesign.render_redesign_briefing(
        _context(raw_workouts), TODAY, retrieval="topics: training · 5 claims"
    )

    assert "Redesign Briefing" in note
    assert "no API key" in note
    assert "Diagnosis" in note
    assert "Per-draft edits" in note
    # The corpus gap is declared up front, not buried (E2 honesty contract).
    assert "Corpus gap — programming content not ingested yet" in note
    assert "topics: training · 5 claims" in note
    # Provenance rules ride along (E5 contract).
    assert "[cited: [[id#^claim-xx]]]" in note
    assert "never invent a citation link" in note
    assert redesign.redesign_briefing_path(TODAY).endswith("Redesign Briefing.md")


# -- CLI -------------------------------------------------------------------


def _write_cache(tmp_path: Path, raw_workouts: dict, *, routines: dict) -> Path:
    import json

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "workouts.json").write_text(json.dumps(raw_workouts), encoding="utf-8")
    (data_dir / "routines.json").write_text(json.dumps(routines), encoding="utf-8")
    return data_dir


def _write_config(tmp_path: Path) -> Path:
    config = tmp_path / "config.toml"
    config.write_text(
        f"[vault]\npath = '{tmp_path}'\nsubfolder = \"Hevy\"\n"
        f"[sync]\ndata_dir = '{tmp_path / 'data'}'\n",
        encoding="utf-8",
    )
    return config


def test_cli_guide_redesign_writes_briefing_and_drafts(
    tmp_path: Path, raw_workouts: dict, capsys: pytest.CaptureFixture
) -> None:
    from hevy_brain.cli import main

    _write_cache(
        tmp_path, raw_workouts, routines={"r1": make_routine("r1", "Push Day")}
    )
    config = _write_config(tmp_path)

    code = main(["--config", str(config), "guide", "redesign"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Redesign briefing written" in out
    assert "Draft written" in out
    briefings = list((tmp_path / "Hevy" / "Coach").glob("* Redesign Briefing.md"))
    assert len(briefings) == 1
    drafts = list((tmp_path / "Hevy" / "Routines" / "Drafts").glob("Redesign*.md"))
    assert len(drafts) == 1
    text = briefings[0].read_text(encoding="utf-8")
    assert "Push Day: 2 sessions" in text
    assert "Corpus gap" in text


def test_cli_guide_redesign_empty_cache(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from hevy_brain.cli import main

    config = _write_config(tmp_path)

    code = main(["--config", str(config), "guide", "redesign"])

    assert code == 1
    assert "Cache is empty" in capsys.readouterr().err


def test_cli_guide_redesign_without_routines_still_briefs(
    tmp_path: Path, raw_workouts: dict, capsys: pytest.CaptureFixture
) -> None:
    from hevy_brain.cli import main

    _write_cache(tmp_path, raw_workouts, routines={})
    config = _write_config(tmp_path)

    code = main(["--config", str(config), "guide", "redesign"])

    assert code == 0
    assert "Redesign briefing written" in capsys.readouterr().out
    briefing = next((tmp_path / "Hevy" / "Coach").glob("* Redesign Briefing.md"))
    assert "None written" in briefing.read_text(encoding="utf-8")
