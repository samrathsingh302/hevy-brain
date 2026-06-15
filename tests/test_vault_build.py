"""End-to-end vault generation tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.config import Config
from hevy_brain.models import build_records
from hevy_brain.store.cache import CacheStore
from hevy_brain.vault.build import build_vault
from hevy_brain.vault.dashboards import render_dashboard
from hevy_brain.vault.exercises import render_exercise_note
from hevy_brain.vault.workouts import workout_note_paths

TODAY = date(2026, 6, 10)


def _config(tmp_path: Path) -> Config:
    return Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
    )


def _store(tmp_path: Path, raw_workouts: dict) -> CacheStore:
    store = CacheStore(tmp_path / "data")
    for workout in raw_workouts.values():
        store.upsert_workout(workout)
    store.set_measurements([{"date": "2026-06-01", "weight_kg": 78.0}])
    return store


def test_build_vault_generates_all_notes(tmp_path: Path, raw_workouts: dict) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    changed = build_vault(config, store, today=TODAY)

    root = config.vault_root
    assert changed["workouts"] == 3
    assert (root / "Dashboard.md").is_file()
    assert (root / "Workouts" / "2026-06-08 Push Day.md").is_file()
    assert (root / "Exercises" / "Bench Press (Barbell).md").is_file()
    assert (root / "Measurements" / "Body Log.md").is_file()
    assert list((root / "Reviews").glob("*Weekly Review.md"))
    assert (root / "Reviews" / "2026 Year in Review.md").is_file()

    workout_text = (root / "Workouts" / "2026-06-08 Push Day.md").read_text(
        encoding="utf-8"
    )
    assert "hevy_id: w3" in workout_text
    assert "type: hevy-workout" in workout_text
    assert "[[Bench Press (Barbell)]]" in workout_text
    assert "PR" in workout_text  # w3 sets a bench weight PR
    assert "push workout <file> --update" in workout_text  # fix-up callout

    dashboard = (root / "Dashboard.md").read_text(encoding="utf-8")
    assert "3** workouts" in dashboard or "**3** workouts" in dashboard


def test_charts_render_in_dashboard_and_exercise_notes(
    tmp_path: Path, raw_workouts: dict
) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)

    root = config.vault_root
    dashboard = (root / "Dashboard.md").read_text(encoding="utf-8")
    assert "xychart-beta" in dashboard
    assert "Volume trend (last 12 weeks)" in dashboard

    # Bench is performed in w1 and w3 -> 2 loaded sessions -> an e1RM trend.
    bench = (root / "Exercises" / "Bench Press (Barbell).md").read_text(
        encoding="utf-8"
    )
    assert "xychart-beta" in bench
    assert "est. 1RM trend" in bench


def test_charts_omitted_when_disabled(tmp_path: Path, raw_workouts: dict) -> None:
    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
        charts_enabled=False,
    )
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)

    root = config.vault_root
    dashboard = (root / "Dashboard.md").read_text(encoding="utf-8")
    assert "xychart-beta" not in dashboard
    assert "Volume trend" not in dashboard  # no orphan heading either
    bench = (root / "Exercises" / "Bench Press (Barbell).md").read_text(
        encoding="utf-8"
    )
    assert "xychart-beta" not in bench
    assert "est. 1RM trend" not in bench  # no orphan heading either


def test_consistency_heatmap_renders_in_dashboard(
    tmp_path: Path, raw_workouts: dict
) -> None:
    # raw_workouts spans 3 ISO weeks (25/05, 01/06, 08/06) -> >=2 trained weeks.
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)

    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "## Consistency (last 26 weeks)" in dashboard
    assert "```text" in dashboard
    assert "Legend:" in dashboard


def test_consistency_heatmap_omitted_when_disabled(
    tmp_path: Path, raw_workouts: dict
) -> None:
    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
        charts_heatmap_enabled=False,
    )
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)

    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "## Consistency" not in dashboard  # no orphan heading


def test_consistency_heatmap_build_is_idempotent(
    tmp_path: Path, raw_workouts: dict
) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)
    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "## Consistency (last 26 weeks)" in dashboard  # heatmap present...

    second = build_vault(config, store, today=TODAY)
    assert sum(second.values()) == 0  # ...and a same-today rebuild is a no-op


def test_enabled_charts_omit_heading_when_series_too_short() -> None:
    """F7 at the render boundary: charts ON, but a None chart (too few points)
    must leave NO orphan heading — the case the disabled test can't reach
    because the disabled guard short-circuits before chart_section is called."""
    records = build_records(
        {
            "a": make_workout(
                "a",
                start="2026-06-08T17:00:00+00:00",
                end="2026-06-08T18:00:00+00:00",
                exercises=[make_exercise("Bench", "T-B", [make_set(60, 8)])],
            )
        }
    )
    # One loaded session -> e1RM chart is None even with charts enabled.
    note = render_exercise_note(
        exercise_histories(records)["Bench"], {}, e1rm_max_points=10
    )
    assert "xychart-beta" not in note
    assert "est. 1RM trend" not in note

    # Empty window -> all-zero volume series -> chart None, heading omitted.
    dashboard = render_dashboard([], {}, {}, {}, TODAY, volume_weeks=12)
    assert "xychart-beta" not in dashboard
    assert "Volume trend" not in dashboard


def _progression_workouts() -> dict:
    """Bench across three weeks at 60 kg x 8 -> a 'next session target'."""
    raw = {}
    for i, day in enumerate(("2026-05-25", "2026-06-01", "2026-06-08")):
        raw[f"p{i}"] = make_workout(
            f"p{i}",
            "Push Day",
            start=f"{day}T17:00:00+00:00",
            end=f"{day}T18:00:00+00:00",
            exercises=[make_exercise(sets=[make_set(60, 8)])],
        )
    return raw


def test_progression_target_renders_in_exercise_note(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, _progression_workouts())

    build_vault(config, store, today=TODAY)

    bench = (config.vault_root / "Exercises" / "Bench Press (Barbell).md").read_text(
        encoding="utf-8"
    )
    assert "Next session target" in bench
    assert "60 kg × 9" in bench


def test_progression_disabled_omits_section(tmp_path: Path) -> None:
    config = Config(
        base_dir=tmp_path,
        vault_path=tmp_path / "vault",
        data_dir=tmp_path / "data",
        progression_enabled=False,
    )
    store = _store(tmp_path, _progression_workouts())

    build_vault(config, store, today=TODAY)

    bench = (config.vault_root / "Exercises" / "Bench Press (Barbell).md").read_text(
        encoding="utf-8"
    )
    assert "Next session target" not in bench


def test_progression_build_is_idempotent(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, _progression_workouts())

    build_vault(config, store, today=TODAY)
    second = build_vault(config, store, today=TODAY)

    assert sum(second.values()) == 0


def _deload_workouts() -> dict:
    """Eight unbroken weekly weeks of flat bench ending at TODAY's ISO week ->
    a long consecutive run + a plateau (flat est-1RM)."""
    from datetime import timedelta

    last_monday = date(2026, 6, 8)  # Mon of TODAY's (2026-06-10) ISO week
    raw = {}
    for i in range(8):
        day = (last_monday - timedelta(weeks=i)).isoformat()
        raw[day] = make_workout(
            f"d-{day}",
            "Push Day",
            start=f"{day}T17:00:00+00:00",
            end=f"{day}T18:00:00+00:00",
            exercises=[make_exercise(sets=[make_set(100, 5)])],
        )
    return raw


def test_deload_callout_fires_through_build(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, _deload_workouts())

    build_vault(config, store, today=TODAY)

    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "> [!note] Deload readiness" in dashboard
    assert "consecutive training weeks" in dashboard
    assert (
        "general training-science heuristic, not personalised or medical advice"
        in dashboard
    )


def test_deload_callout_silent_on_short_history(
    tmp_path: Path, raw_workouts: dict
) -> None:
    # The real-shaped fixture has only 3 workouts across 3 weeks (run < 6) ->
    # the deload section must never appear through the full build path.
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)

    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "Deload readiness" not in dashboard


def test_deload_callout_silent_when_lapsed(tmp_path: Path) -> None:
    # Same 8-week run, but assessed 60 days later -> a lapse -> silent.
    config = _config(tmp_path)
    store = _store(tmp_path, _deload_workouts())

    build_vault(config, store, today=date(2026, 8, 9))

    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "Deload readiness" not in dashboard


def test_deload_build_is_idempotent(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, _deload_workouts())

    build_vault(config, store, today=TODAY)
    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "Deload readiness" in dashboard  # callout present...

    second = build_vault(config, store, today=TODAY)
    assert sum(second.values()) == 0  # ...and a same-today rebuild is a no-op


def test_volume_landmarks_render_in_dashboard(
    tmp_path: Path, raw_workouts: dict
) -> None:
    # raw_workouts' last session (2026-06-08) is 2 days before TODAY -> recent,
    # so the default-config landmark bands produce a table through the build.
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)

    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "## Volume landmarks" in dashboard
    assert "General guideline, not personalised advice" in dashboard
    assert "| Muscle group | Sets/wk | Status |" in dashboard


def test_volume_landmarks_degrade_when_lapsed(
    tmp_path: Path, raw_workouts: dict
) -> None:
    # Same fixture assessed 60 days later -> lapsed -> honest line, no table.
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=date(2026, 8, 9))

    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "## Volume landmarks" in dashboard
    assert "No recent training to assess against volume landmarks." in dashboard
    assert "Sets/wk" not in dashboard  # no table when lapsed


def test_volume_landmarks_build_is_idempotent(
    tmp_path: Path, raw_workouts: dict
) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)
    dashboard = (config.vault_root / "Dashboard.md").read_text(encoding="utf-8")
    assert "## Volume landmarks" in dashboard  # table present...

    second = build_vault(config, store, today=TODAY)
    assert sum(second.values()) == 0  # ...and a same-today rebuild is a no-op


def test_dashboard_lapse_callout(raw_workouts: dict) -> None:
    records = build_records(raw_workouts)  # last session 2026-06-08
    histories = exercise_histories(records)

    # Recent training (2 days) with nudging enabled -> no callout.
    recent = render_dashboard(
        records, histories, {}, {}, date(2026, 6, 10), lapse_nudge_days=7
    )
    assert "since your last session" not in recent

    # 20 quiet days -> a lapse callout that points at guide return.
    lapsed = render_dashboard(
        records, histories, {}, {}, date(2026, 6, 28), lapse_nudge_days=7
    )
    assert "20 days" in lapsed
    assert "guide return" in lapsed


def test_generated_workout_note_round_trips(tmp_path: Path, raw_workouts: dict) -> None:
    """A managed workout note from the real build path must parse back into a
    no-op PUT body — the fix-up round-trip guarantee, end to end."""
    from hevy_brain.writeback.hevy_push import parse_workout_note, workout_diff

    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)
    build_vault(config, store, today=TODAY)

    note = config.vault_root / "Workouts" / "2026-06-08 Push Day.md"
    workout_id, body = parse_workout_note(note)

    assert workout_id == "w3"
    assert workout_diff(raw_workouts["w3"], body) == []


def test_build_vault_is_idempotent(tmp_path: Path, raw_workouts: dict) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)

    build_vault(config, store, today=TODAY)
    second = build_vault(config, store, today=TODAY)

    assert sum(second.values()) == 0


def test_archived_workout_note_moves_to_archive(
    tmp_path: Path, raw_workouts: dict
) -> None:
    config = _config(tmp_path)
    store = _store(tmp_path, raw_workouts)
    build_vault(config, store, today=TODAY)

    store.archive_workout("w2")
    changed = build_vault(config, store, today=TODAY)

    root = config.vault_root
    assert changed["archived"] == 1
    assert not (root / "Workouts" / "2026-06-01 Pull Day.md").exists()
    assert (root / "Archive" / "2026-06-01 Pull Day.md").exists()


def test_duplicate_title_same_day_gets_suffix() -> None:
    w_a = make_workout(
        "aaaa1111",
        "Push Day",
        start="2026-06-08T07:00:00+00:00",
        end="2026-06-08T08:00:00+00:00",
    )
    w_b = make_workout(
        "bbbb2222",
        "Push Day",
        start="2026-06-08T17:00:00+00:00",
        end="2026-06-08T18:00:00+00:00",
    )
    from hevy_brain.models import build_records

    paths = workout_note_paths(build_records({w["id"]: w for w in (w_a, w_b)}))

    assert paths["aaaa1111"] == "Workouts/2026-06-08 Push Day.md"
    assert paths["bbbb2222"] == "Workouts/2026-06-08 Push Day (bbbb2222).md"
