"""Tests for guide return: drafts, briefing, and the CLI command (E1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from conftest import make_routine, make_routine_exercise, make_routine_set

from hevy_brain.analytics.comeback import lapse_status, pre_lapse_baselines
from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.coach import comeback
from hevy_brain.knowledge import Claim
from hevy_brain.models import build_records
from hevy_brain.vault.drafts import (
    generate_return_drafts,
    render_return_draft,
    scale_exercises,
    scale_weight,
    select_return_routines,
)
from hevy_brain.vault.writer import VaultWriter
from hevy_brain.writeback.hevy_push import parse_routine_note

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


# -- load scaling ----------------------------------------------------------


def test_scale_weight_rounds_to_plate_steps() -> None:
    assert scale_weight(100, 0.6) == 60.0
    assert scale_weight(84, 0.6) == 50.0  # 50.4 -> nearest 2.5
    assert scale_weight(62.5, 0.6) == 37.5
    assert scale_weight(3, 0.6) == 2.5  # never below one plate step


def test_scale_weight_never_exceeds_the_original_load() -> None:
    # A return week must not load heavier than pre-lapse: weights at or
    # below one plate step pass through instead of rounding UP to the step.
    assert scale_weight(2.0, 0.6) == 2.0
    assert scale_weight(1.0, 0.6) == 1.0
    assert scale_weight(2.5, 0.6) == 2.5


def test_scale_exercises_keeps_bodyweight_and_structure() -> None:
    spec = [
        {
            "name": "Pull Up",
            "exercise_template_id": "T-PULLUP",
            "rest_seconds": 90,
            "sets": [{"type": "normal", "reps": 8}],
        },
        {
            "name": "Bench Press (Barbell)",
            "exercise_template_id": "T-BENCH",
            "sets": [
                {"type": "normal", "weight_kg": 80.0, "reps": 5},
                {
                    "type": "normal",
                    "weight_kg": 80.0,
                    "rep_range": {"start": 5, "end": 8},
                },
            ],
        },
    ]

    scaled = scale_exercises(spec, 0.6)

    # Bodyweight set untouched, no weight invented.
    assert "weight_kg" not in scaled[0]["sets"][0]
    assert scaled[0]["rest_seconds"] == 90
    # Weighted sets scaled, reps/rep_range preserved.
    assert scaled[1]["sets"][0] == {"type": "normal", "weight_kg": 47.5, "reps": 5}
    assert scaled[1]["sets"][1]["rep_range"] == {"start": 5, "end": 8}
    # The original spec is not mutated.
    assert spec[1]["sets"][0]["weight_kg"] == 80.0


# -- routine selection -----------------------------------------------------


def test_select_return_routines_prefers_pre_lapse_titles() -> None:
    routines = {
        "r1": make_routine("r1", "Push Day", updated_at="2026-06-01T09:00:00+00:00"),
        "r2": make_routine("r2", "Legs", updated_at="2026-06-09T09:00:00+00:00"),
        "r3": make_routine("r3", "Pull Day", updated_at="2026-06-02T09:00:00+00:00"),
    }

    chosen = select_return_routines(routines, ["Push Day", "Pull Day"], limit=2)

    assert [r["id"] for r in chosen] == ["r3", "r1"]  # matched, newest first


def test_select_return_routines_fills_with_recently_updated() -> None:
    routines = {
        "r1": make_routine("r1", "Push Day", updated_at="2026-06-01T09:00:00+00:00"),
        "r2": make_routine("r2", "Legs", updated_at="2026-06-09T09:00:00+00:00"),
    }

    chosen = select_return_routines(routines, ["Push Day"], limit=2)

    assert [r["id"] for r in chosen] == ["r1", "r2"]


def test_select_return_routines_skips_unpushable_routines() -> None:
    # A draft of these would fail parse_routine_note — never offer one.
    no_exercises = make_routine("r1", "Empty", exercises=[])
    no_sets = make_routine("r2", "No Sets", exercises=[make_routine_exercise(sets=[])])
    no_template = make_routine(
        "r3", "No Template", exercises=[make_routine_exercise(template_id="")]
    )
    good = make_routine("r4", "Push Day")
    routines = {r["id"]: r for r in (no_exercises, no_sets, no_template, good)}

    chosen = select_return_routines(routines, [], limit=4)

    assert [r["id"] for r in chosen] == ["r4"]


# -- draft notes -----------------------------------------------------------


def test_render_return_draft_round_trips_through_push_parser(
    tmp_path: Path,
) -> None:
    routine = make_routine(
        "r9",
        "Push Day A",
        exercises=[
            make_routine_exercise(
                sets=[make_routine_set(80, 5), make_routine_set(80, 5)]
            )
        ],
    )

    rel_path, content = render_return_draft(routine, fraction=0.6)

    assert rel_path == "Routines/Drafts/Return Week 1 — Push Day A.md"
    writer = VaultWriter(tmp_path)
    writer.write(rel_path, content)

    # The draft must parse with the slice-1 round-trip, ready to push.
    routine_id, body = parse_routine_note(tmp_path / rel_path)
    assert routine_id == "r9"
    assert body["routine"]["title"] == "Return Week 1 — Push Day A"
    assert body["routine"]["exercises"][0]["sets"][0]["weight_kg"] == 47.5


def test_render_return_draft_body_keeps_original_loads() -> None:
    routine = make_routine(
        "r9",
        "Push Day A",
        exercises=[make_routine_exercise(sets=[make_routine_set(80, 5)])],
    )

    _, content = render_return_draft(routine, fraction=0.6)

    # No-data-loss: the original load is visible next to the week-1 load,
    # the PUT warning is explicit, and the fraction is honestly labelled.
    assert "80 kg × 5" in content
    assert "47.5 kg × 5" in content
    assert "replaces" in content
    assert "--dry-run" in content
    assert "[general-knowledge]" in content


def test_render_return_draft_preserves_routine_notes(tmp_path: Path) -> None:
    routine = make_routine("r9", "Push Day A")
    routine["notes"] = "Focus on tempo."

    rel_path, content = render_return_draft(routine, fraction=0.6)
    writer = VaultWriter(tmp_path)
    writer.write(rel_path, content)

    # PUT is a full replacement: a draft without the routine's notes would
    # silently wipe them in Hevy on push.
    _, body = parse_routine_note(tmp_path / rel_path)
    assert body["routine"]["notes"] == "Focus on tempo."


def test_generate_return_drafts_suffixes_duplicate_titles(tmp_path: Path) -> None:
    writer = VaultWriter(tmp_path)
    routines = {
        "ralpha111": make_routine(
            "ralpha111", "Push Day", updated_at="2026-06-09T09:00:00+00:00"
        ),
        "rbeta2222": make_routine(
            "rbeta2222", "Push Day", updated_at="2026-06-01T09:00:00+00:00"
        ),
    }

    written, skipped = generate_return_drafts(writer, routines, [], fraction=0.6)

    assert not skipped
    assert written == [
        "Routines/Drafts/Return Week 1 — Push Day.md",
        "Routines/Drafts/Return Week 1 — Push Day (rbeta222).md",
    ]


def test_generate_return_drafts_is_write_once(tmp_path: Path) -> None:
    writer = VaultWriter(tmp_path)
    routines = {"r1": make_routine("r1", "Push Day")}

    written, skipped = generate_return_drafts(
        writer, routines, ["Push Day"], fraction=0.6
    )
    assert len(written) == 1
    assert not skipped

    draft = tmp_path / written[0]
    draft.write_text(draft.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")

    written2, skipped2 = generate_return_drafts(
        writer, routines, ["Push Day"], fraction=0.6
    )
    assert not written2
    assert skipped2 == written
    assert "edited" in draft.read_text(encoding="utf-8")


# -- briefing --------------------------------------------------------------


def _context(raw_workouts: dict, **kwargs) -> str:
    records = build_records(raw_workouts)
    histories = exercise_histories(records)
    lapse = lapse_status(records, TODAY)
    assert lapse is not None
    baselines = pre_lapse_baselines(records, histories, weeks=4)
    return comeback.build_return_context(
        lapse, baselines, today=TODAY, load_fraction=0.6, **kwargs
    )


def test_build_return_context_grounds_the_numbers(raw_workouts: dict) -> None:
    context = _context(raw_workouts)

    assert "63 days ago" in context
    assert "2026-06-08" in context
    assert "800 kg/week" in context
    assert "Bench Press (Barbell)" in context
    assert "60%" in context
    assert "[general-knowledge]" in context


def test_build_return_context_lists_drafts_and_claims(raw_workouts: dict) -> None:
    context = _context(
        raw_workouts,
        draft_paths=["Routines/Drafts/Return Week 1 — Push Day.md"],
        knowledge=_claims(),
    )

    assert "[[Routines/Drafts/Return Week 1 — Push Day.md]]" in context
    assert "--dry-run" in context
    assert "[[xJ0IBzCjEPk#^claim-07]]" in context


def test_build_return_context_flags_empty_corpus(raw_workouts: dict) -> None:
    context = _context(raw_workouts, knowledge=[])

    assert "No cited claims" in context


def test_render_return_briefing_is_self_contained(raw_workouts: dict) -> None:
    note = comeback.render_return_briefing(_context(raw_workouts), TODAY)

    assert "Return Briefing" in note
    assert "no API key" in note
    assert "Week-by-week ramp" in note
    assert "AVOID list" in note
    assert "63 days ago" in note
    # Provenance rules ride along (E5 contract).
    assert "[cited: [[id#^claim-xx]]]" in note
    assert "never invent a citation link" in note
    assert comeback.return_briefing_path(TODAY).endswith("Return Briefing.md")


# -- CLI -------------------------------------------------------------------


def _write_cache(tmp_path: Path, raw_workouts: dict, *, routines: dict) -> Path:
    import json

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "workouts.json").write_text(json.dumps(raw_workouts), encoding="utf-8")
    (data_dir / "routines.json").write_text(json.dumps(routines), encoding="utf-8")
    return data_dir


def test_cli_guide_return_writes_briefing_and_drafts(
    tmp_path: Path, raw_workouts: dict, capsys: pytest.CaptureFixture
) -> None:
    from hevy_brain.cli import main

    _write_cache(
        tmp_path, raw_workouts, routines={"r1": make_routine("r1", "Push Day")}
    )
    (tmp_path / "config.toml").write_text(
        f"[vault]\npath = '{tmp_path}'\nsubfolder = \"Hevy\"\n"
        f"[sync]\ndata_dir = '{tmp_path / 'data'}'\n"
        # Fixture workouts are dated near the real clock — any gap counts.
        "[guide]\nlapse_days = 1\n",
        encoding="utf-8",
    )

    code = main(["--config", str(tmp_path / "config.toml"), "guide", "return"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Return briefing written" in out
    assert "Draft written" in out
    briefings = list((tmp_path / "Hevy" / "Coach").glob("* Return Briefing.md"))
    assert len(briefings) == 1
    drafts = list((tmp_path / "Hevy" / "Routines" / "Drafts").glob("*.md"))
    assert len(drafts) == 1
    # The real lapse (fixtures end 2026-06-08) shows up in the briefing.
    assert "days ago" in briefings[0].read_text(encoding="utf-8")


def test_cli_guide_return_empty_cache(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from hevy_brain.cli import main

    (tmp_path / "config.toml").write_text(
        f"[vault]\npath = '{tmp_path}'\nsubfolder = \"Hevy\"\n"
        f"[sync]\ndata_dir = '{tmp_path / 'data'}'\n",
        encoding="utf-8",
    )

    code = main(["--config", str(tmp_path / "config.toml"), "guide", "return"])

    assert code == 1
    assert "Cache is empty" in capsys.readouterr().err


def test_cli_guide_return_without_routines_still_briefs(
    tmp_path: Path, raw_workouts: dict, capsys: pytest.CaptureFixture
) -> None:
    from hevy_brain.cli import main

    _write_cache(tmp_path, raw_workouts, routines={})
    (tmp_path / "config.toml").write_text(
        f"[vault]\npath = '{tmp_path}'\nsubfolder = \"Hevy\"\n"
        f"[sync]\ndata_dir = '{tmp_path / 'data'}'\n"
        "[guide]\nlapse_days = 1\n",
        encoding="utf-8",
    )

    code = main(["--config", str(tmp_path / "config.toml"), "guide", "return"])

    assert code == 0
    assert "Return briefing written" in capsys.readouterr().out
    briefing = next((tmp_path / "Hevy" / "Coach").glob("* Return Briefing.md"))
    assert "None written" in briefing.read_text(encoding="utf-8")


def test_cli_guide_return_no_lapse(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from datetime import UTC, datetime, timedelta

    from conftest import make_workout

    from hevy_brain.cli import main

    start = (datetime.now(tz=UTC) - timedelta(days=1)).isoformat()
    end = datetime.now(tz=UTC).isoformat()
    recent = make_workout("w-now", "Push Day", start=start, end=end)
    _write_cache(tmp_path, {"w-now": recent}, routines={})
    (tmp_path / "config.toml").write_text(
        f"[vault]\npath = '{tmp_path}'\nsubfolder = \"Hevy\"\n"
        f"[sync]\ndata_dir = '{tmp_path / 'data'}'\n",
        encoding="utf-8",
    )

    code = main(["--config", str(tmp_path / "config.toml"), "guide", "return"])

    assert code == 0
    assert "No lapse detected" in capsys.readouterr().out
    assert not (tmp_path / "Hevy" / "Coach").exists()
