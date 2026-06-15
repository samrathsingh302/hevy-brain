"""Tests for the volume-landmark check (general-knowledge, lapse-safe).

The check must classify recent weekly sets/muscle-group against the user's
configurable MEV/MAV/MRV bands, skip groups with no band, always exclude
``other``, and — most importantly for the real ~65-day-lapsed account — degrade
honestly to a "no recent training" line rather than reporting stale numbers.
"""

from __future__ import annotations

from datetime import date, timedelta

from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics import landmarks
from hevy_brain.models import build_records
from hevy_brain.vault.dashboards import _landmarks_lines, render_dashboard

# A Wednesday: stats.week_start(TODAY) == 2026-06-08 (Mon of that ISO week).
TODAY = date(2026, 6, 10)

_LABEL = "General guideline, not personalised advice"

# Compact bands for tests: chest crosses at 8/14/22, easy to target by set count.
_BANDS = landmarks.default_bands()


def _weekly_sets(
    *,
    weeks: int,
    sets_per_session: int,
    last_monday: date,
    title: str = "Bench Press (Barbell)",
    template_id: str = "T-BENCH",
) -> dict:
    """One workout per ISO week for ``weeks`` consecutive weeks ending at
    ``last_monday``, each holding ``sets_per_session`` working sets of one
    exercise. Keyed by date so merging two dicts never collides.
    """
    raw: dict = {}
    for i in range(weeks):
        day = last_monday - timedelta(weeks=i)
        raw[f"{title}-{day.isoformat()}"] = make_workout(
            workout_id=f"w-{title}-{day.isoformat()}",
            start=f"{day.isoformat()}T17:00:00+00:00",
            end=f"{day.isoformat()}T18:00:00+00:00",
            exercises=[
                make_exercise(
                    title,
                    template_id,
                    sets=[make_set(60, 8) for _ in range(sets_per_session)],
                )
            ],
        )
    return raw


def _status(raw: dict, *, today: date = TODAY, weeks: int = 4, bands=None):
    records = build_records(raw)
    return landmarks.landmark_status(
        records, today, _BANDS if bands is None else bands, landmark_weeks=weeks
    )


def _row(status: dict, group: str) -> dict | None:
    return next((r for r in status["rows"] if r["group"] == group), None)


# --- classification across all four bands ------------------------------------
# 4 trained weeks, so weekly chest sets = (4 * sets_per_session) / 4 = sets_per_session.


def test_classifies_below_mev() -> None:
    # chest MEV is 8; 4 weeks x 1 set = 1.0 set/wk -> below MEV.
    status = _status(_weekly_sets(weeks=4, sets_per_session=1, last_monday=date(2026, 6, 8)))
    assert status is not None
    assert status["lapsed"] is False
    chest = _row(status, "chest")
    assert chest is not None
    assert chest["sets_per_week"] == 1.0
    assert chest["status"] == "below MEV"


def test_classifies_mev_to_mav() -> None:
    # 10 set/wk sits in chest's [8, 14) band.
    status = _status(_weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8)))
    chest = _row(status, "chest")
    assert chest is not None
    assert chest["sets_per_week"] == 10.0
    assert chest["status"] == "MEV-MAV (maintenance->growth)"


def test_classifies_mav_to_mrv() -> None:
    # 18 set/wk sits in chest's [14, 22) band.
    status = _status(_weekly_sets(weeks=4, sets_per_session=18, last_monday=date(2026, 6, 8)))
    chest = _row(status, "chest")
    assert chest is not None
    assert chest["sets_per_week"] == 18.0
    assert chest["status"] == "MAV-MRV (productive)"


def test_classifies_above_mrv() -> None:
    # 24 set/wk is at/above chest's MRV of 22 -> high.
    status = _status(_weekly_sets(weeks=4, sets_per_session=24, last_monday=date(2026, 6, 8)))
    chest = _row(status, "chest")
    assert chest is not None
    assert chest["sets_per_week"] == 24.0
    assert chest["status"] == "above MRV (high)"


def test_lower_edge_is_inclusive() -> None:
    # Exactly on MEV (8) reads as maintenance/growth, not below MEV.
    status = _status(_weekly_sets(weeks=4, sets_per_session=8, last_monday=date(2026, 6, 8)))
    assert _row(status, "chest")["status"] == "MEV-MAV (maintenance->growth)"


# --- a config override MOVING a band changes the classification --------------


def test_override_band_moves_classification() -> None:
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    # Default: 10 set/wk is MEV-MAV. Raise MEV above 10 -> the same data reads
    # as below MEV (the bands are the user's to own).
    moved = {**_BANDS, "chest": {"mev": 12.0, "mav": 18.0, "mrv": 26.0}}
    default_status = _status(raw)
    moved_status = _status(raw, bands=moved)
    assert _row(default_status, "chest")["status"] == "MEV-MAV (maintenance->growth)"
    assert _row(moved_status, "chest")["status"] == "below MEV"


# --- a present group with NO configured band is SKIPPED (no crash) -----------


def test_present_group_without_band_is_skipped() -> None:
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    # Drop chest from the bands entirely; the group is present in training but
    # unconfigured -> it must be skipped, not crash, not invented.
    no_chest = {g: b for g, b in _BANDS.items() if g != "chest"}
    status = _status(raw, bands=no_chest)
    assert status is not None
    assert _row(status, "chest") is None
    assert status["rows"] == []  # the only trained group had no band


# --- the `other` group is ALWAYS excluded ------------------------------------


def test_other_group_excluded() -> None:
    # "Sled Push" matches no keyword and has no template -> muscle_group "other".
    raw = _weekly_sets(
        weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8),
        title="Sled Push", template_id="T-SLED",
    )
    # Give "other" a band so the ONLY reason to exclude it is the hard rule.
    bands = {**_BANDS, "other": {"mev": 1.0, "mav": 2.0, "mrv": 3.0}}
    status = _status(raw, bands=bands)
    assert status is not None
    assert _row(status, "other") is None  # excluded even with a band configured


# --- the lapse / empty-window honest degrade ---------------------------------


def test_lapsed_account_degrades_honestly() -> None:
    # Real-shaped lapse: last workout ~65 days before today.
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 4, 6))
    status = _status(raw, today=TODAY)
    assert status is not None
    assert status["lapsed"] is True
    assert status["rows"] == []  # never classify stale numbers


def test_empty_history_degrades_honestly() -> None:
    status = landmarks.landmark_status([], TODAY, _BANDS, landmark_weeks=4)
    assert status is not None
    assert status["lapsed"] is True


def test_no_bands_degrades_honestly() -> None:
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    status = _status(raw, bands={})
    assert status is not None
    assert status["lapsed"] is True


def test_future_dated_last_workout_degrades() -> None:
    # Last workout after today (a backdated rebuild) -> not assessable.
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=TODAY + timedelta(weeks=1))
    assert _status(raw)["lapsed"] is True


def test_disabled_returns_none() -> None:
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    assert _status(raw, weeks=0) is None  # landmark_weeks <= 0 -> disabled


# --- effective-weeks division (short window not diluted) ---------------------


def test_short_window_divides_by_weeks_covered() -> None:
    # Only 2 trained weeks but a 4-week window: dividing by the constant 4 would
    # halve the rate. effective_weeks = 2 -> (2 * 12) / 2 = 12 set/wk.
    raw = _weekly_sets(weeks=2, sets_per_session=12, last_monday=date(2026, 6, 8))
    status = _status(raw, weeks=4)
    assert status["effective_weeks"] == 2
    assert _row(status, "chest")["sets_per_week"] == 12.0


def test_warmups_are_not_counted() -> None:
    # 4 weeks, each: 10 working + 5 warm-up chest sets. Warm-ups must not inflate
    # the weekly figure -> still 10 set/wk, not 15.
    raw: dict = {}
    for i in range(4):
        day = date(2026, 6, 8) - timedelta(weeks=i)
        sets = [make_set(60, 8) for _ in range(10)] + [
            make_set(40, 10, type="warmup") for _ in range(5)
        ]
        raw[day.isoformat()] = make_workout(
            workout_id=f"w-{day.isoformat()}",
            start=f"{day.isoformat()}T17:00:00+00:00",
            end=f"{day.isoformat()}T18:00:00+00:00",
            exercises=[make_exercise("Bench Press (Barbell)", "T-BENCH", sets=sets)],
        )
    assert _row(_status(raw), "chest")["sets_per_week"] == 10.0


# --- rendering: label, table, honest degrade, ordering -----------------------


def test_render_includes_general_knowledge_label() -> None:
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    lines = _landmarks_lines(
        build_records(raw), TODAY, _BANDS,
        landmark_weeks=4, templates=None, overrides=None,
    )
    text = "\n".join(lines)
    assert "## Volume landmarks" in text
    assert _LABEL in text
    assert "`config.toml`" in text
    assert "| chest | 10.0 | MEV-MAV (maintenance->growth) |" in text


def test_render_lapse_line_not_a_table() -> None:
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 4, 6))
    text = "\n".join(
        _landmarks_lines(
            build_records(raw), TODAY, _BANDS,
            landmark_weeks=4, templates=None, overrides=None,
        )
    )
    assert "No recent training to assess against volume landmarks." in text
    assert _LABEL in text  # the guideline framing still shows
    assert "Sets/wk" not in text  # but no table is drawn


def test_render_omitted_when_no_bands() -> None:
    # An unconfigured caller (no bands) gets NO section at all (no orphan heading).
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    assert _landmarks_lines(
        build_records(raw), TODAY, {},
        landmark_weeks=4, templates=None, overrides=None,
    ) == []


def test_rows_sorted_descending_then_name() -> None:
    # chest (10/wk) + back via a row exercise (4/wk): chest sorts first.
    chest = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    back = _weekly_sets(
        weeks=4, sets_per_session=4, last_monday=date(2026, 6, 8),
        title="Barbell Row", template_id="T-ROW",
    )
    status = _status({**chest, **back})
    groups = [r["group"] for r in status["rows"]]
    assert groups == ["chest", "back"]  # 10 set/wk before 4 set/wk


# --- dashboard integration + idempotency -------------------------------------


def test_render_dashboard_includes_table_when_recent() -> None:
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    records = build_records(raw)
    out = render_dashboard(
        records, {}, {}, {}, TODAY, landmark_weeks=4, landmark_bands=_BANDS
    )
    assert "## Volume landmarks" in out
    assert _LABEL in out


def test_render_dashboard_silent_by_default() -> None:
    # landmark_weeks defaults to 0 and bands to None -> no section unless threaded.
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    out = render_dashboard(build_records(raw), {}, {}, {}, TODAY)
    assert "Volume landmarks" not in out


def test_render_dashboard_lapse_degrade() -> None:
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 4, 6))
    out = render_dashboard(
        build_records(raw), {}, {}, {}, TODAY, landmark_weeks=4, landmark_bands=_BANDS
    )
    assert "No recent training to assess against volume landmarks." in out


def test_render_dashboard_is_idempotent() -> None:
    raw = _weekly_sets(weeks=4, sets_per_session=10, last_monday=date(2026, 6, 8))
    records = build_records(raw)
    first = render_dashboard(
        records, {}, {}, {}, TODAY, landmark_weeks=4, landmark_bands=_BANDS
    )
    second = render_dashboard(
        records, {}, {}, {}, TODAY, landmark_weeks=4, landmark_bands=_BANDS
    )
    assert first == second
    assert "## Volume landmarks" in first
