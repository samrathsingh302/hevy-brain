"""Tests for the deload-readiness heuristic (general-knowledge, lapse-safe).

The signal must fire only on objective triggers (a long unbroken run of trained
weeks ending near ``today`` + a fatigue signal) and stay silent during a lapse —
the real account is ~65 days lapsed, so this is the behaviour that matters most.
"""

from __future__ import annotations

from datetime import date, timedelta

from conftest import make_exercise, make_set, make_workout

from hevy_brain.analytics import deload
from hevy_brain.analytics.prs import exercise_histories
from hevy_brain.models import build_records
from hevy_brain.vault.dashboards import _deload_callout, render_dashboard

# A Wednesday: stats.week_start(TODAY) == 2026-06-08 (Mon of that ISO week).
TODAY = date(2026, 6, 10)

_LABEL = (
    "This is a general training-science heuristic, not personalised or "
    "medical advice."
)


def _weekly(
    *,
    weeks: int,
    last_monday: date,
    weight: float,
    reps: int = 5,
    rpe: float | None = None,
    title: str = "Bench Press (Barbell)",
    rising: float = 0.0,
) -> dict:
    """One workout per ISO week for ``weeks`` consecutive weeks ending at
    ``last_monday``. ``rising`` adds load each week back-to-front so the most
    recent week is the heaviest (defeats a plateau); ``rising=0`` keeps it flat.
    """
    raw: dict = {}
    for i in range(weeks):
        day = last_monday - timedelta(weeks=i)
        w = weight - rising * i  # most recent (i=0) is heaviest when rising>0
        # Key by date so merging two _weekly() dicts never collides.
        raw[day.isoformat()] = make_workout(
            workout_id=f"w-{day.isoformat()}",
            start=f"{day.isoformat()}T17:00:00+00:00",
            end=f"{day.isoformat()}T18:00:00+00:00",
            exercises=[make_exercise(title, sets=[make_set(w, reps, rpe=rpe)])],
        )
    return raw


def _status(raw: dict, *, today: date = TODAY, weeks: int = 6, rpe: float = 8.5):
    records = build_records(raw)
    histories = exercise_histories(records)
    return deload.deload_status(
        records, histories, today, deload_weeks=weeks, deload_rpe=rpe
    )


# --- the consecutive-week counter -------------------------------------------


def test_consecutive_trained_weeks_counts_unbroken_run() -> None:
    raw = _weekly(weeks=6, last_monday=date(2026, 6, 8), weight=100)
    records = build_records(raw)
    assert deload._consecutive_trained_weeks(records) == 6


def test_consecutive_run_stops_at_a_gap() -> None:
    # Three recent weeks, then a one-week gap, then older training.
    recent = _weekly(weeks=3, last_monday=date(2026, 6, 8), weight=100)
    older = _weekly(weeks=2, last_monday=date(2026, 5, 11), weight=100)
    records = build_records({**recent, **older})  # gap at 2026-05-18 / 25
    assert deload._consecutive_trained_weeks(records) == 3


def test_consecutive_run_empty_history() -> None:
    assert deload._consecutive_trained_weeks([]) == 0


def test_mean_working_rpe_excludes_warmups() -> None:
    # A warm-up set carrying an RPE must not pull the working-set RPE mean — the
    # fatigue trigger reads working sets only. Pins the is_warmup() unification at
    # this site so a future edit can't silently let warm-ups back into the mean.
    raw = {
        "w1": make_workout(
            "w1",
            start="2026-06-08T17:00:00+00:00",
            end="2026-06-08T18:00:00+00:00",
            exercises=[
                make_exercise(
                    sets=[
                        make_set(60, 5, rpe=10.0, type="warmup"),  # excluded
                        make_set(100, 5, rpe=7.0),  # the only working set
                    ]
                )
            ],
        )
    }
    records = build_records(raw)
    assert deload._mean_working_rpe(records, date(2026, 6, 1)) == 7.0


# --- it FIRES -----------------------------------------------------------------


def test_fires_on_plateau_with_long_run() -> None:
    # 9 flat weeks ending at TODAY's week -> long run + a plateau (flat e1RM).
    raw = _weekly(weeks=9, last_monday=date(2026, 6, 8), weight=100, reps=5)
    status = _status(raw)
    assert status is not None
    assert status["weeks"] == 9
    assert status["plateaus"] == ["Bench Press (Barbell)"]


def test_fires_on_high_rpe_without_plateau() -> None:
    # Rising load (no plateau) but every working set is RPE 9 -> RPE trigger.
    raw = _weekly(
        weeks=8, last_monday=date(2026, 6, 8), weight=120, reps=5, rpe=9.0, rising=2.5
    )
    status = _status(raw)
    assert status is not None
    assert status["plateaus"] == []  # rising load defeats the plateau check
    assert status["mean_rpe"] == 9.0


def test_fires_callout_carries_the_general_knowledge_label() -> None:
    raw = _weekly(weeks=9, last_monday=date(2026, 6, 8), weight=100, reps=5)
    records = build_records(raw)
    histories = exercise_histories(records)
    lines = _deload_callout(
        records, histories, TODAY, deload_weeks=6, deload_rpe=8.5, plateau_weeks=4
    )
    text = "\n".join(lines)
    assert "> [!note] Deload readiness" in text
    assert "9 consecutive training weeks" in text
    assert "est-1RM flat on Bench Press (Barbell)" in text
    assert _LABEL in text


def test_high_rpe_callout_reports_the_rpe_figure() -> None:
    raw = _weekly(
        weeks=8, last_monday=date(2026, 6, 8), weight=120, reps=5, rpe=9.0, rising=2.5
    )
    records = build_records(raw)
    histories = exercise_histories(records)
    text = "\n".join(
        _deload_callout(
            records, histories, TODAY, deload_weeks=6, deload_rpe=8.5, plateau_weeks=4
        )
    )
    assert "mean working-set RPE 9.0" in text
    assert _LABEL in text


# --- it is SILENT -------------------------------------------------------------


def test_silent_on_lapsed_account() -> None:
    # 9 unbroken weeks, but the run ENDS ~60 days before today (a real lapse).
    raw = _weekly(weeks=9, last_monday=date(2026, 4, 6), weight=100, reps=5, rpe=9.0)
    assert _status(raw, today=TODAY) is None


def test_silent_on_short_history() -> None:
    # Only 4 weeks ending near today, with high RPE -> run < deload_weeks(6).
    raw = _weekly(weeks=4, last_monday=date(2026, 6, 8), weight=100, reps=5, rpe=9.0)
    assert _status(raw, weeks=6) is None


def test_silent_when_consistent_but_no_fatigue_signal() -> None:
    # 8 unbroken weeks ending near today, rising load (no plateau), no RPE
    # logged -> consistent but no objective fatigue signal.
    raw = _weekly(weeks=8, last_monday=date(2026, 6, 8), weight=140, reps=5, rising=2.5)
    status = _status(raw)
    assert status is None


def test_silent_when_disabled() -> None:
    raw = _weekly(weeks=9, last_monday=date(2026, 6, 8), weight=100, reps=5, rpe=9.0)
    assert _status(raw, weeks=0) is None  # deload_weeks <= 0 -> disabled


def test_silent_on_empty_history() -> None:
    assert deload.deload_status([], {}, TODAY, deload_weeks=6, deload_rpe=8.5) is None


def test_callout_empty_when_silent() -> None:
    raw = _weekly(weeks=9, last_monday=date(2026, 4, 6), weight=100, reps=5, rpe=9.0)
    records = build_records(raw)
    histories = exercise_histories(records)
    assert (
        _deload_callout(
            records, histories, TODAY, deload_weeks=6, deload_rpe=8.5, plateau_weeks=4
        )
        == []
    )


# --- just past the RECENT_DAYS boundary --------------------------------------


def test_fires_when_run_ends_exactly_at_recent_days_boundary() -> None:
    # Last workout exactly RECENT_DAYS (14) before today -> still "near now".
    last = TODAY - timedelta(days=deload.RECENT_DAYS)  # 2026-05-27 (a Wednesday)
    raw = _weekly(weeks=9, last_monday=last, weight=100, reps=5, rpe=9.0)
    # The run is anchored at the last workout's week; it ends within 14 days.
    assert _status(raw) is not None


def test_silent_one_day_past_recent_days() -> None:
    last = TODAY - timedelta(days=deload.RECENT_DAYS + 1)  # 15 days -> lapsed
    raw = _weekly(weeks=9, last_monday=last, weight=100, reps=5, rpe=9.0)
    assert _status(raw) is None


def test_silent_when_last_workout_is_future_dated() -> None:
    # Otherwise firing (9 weeks, high RPE), but the run ends AFTER today (e.g. a
    # backdated historical rebuild). (today - last_date).days is negative, so the
    # gate must still reject it -> you can't be "ready" from training not yet done.
    last = TODAY + timedelta(weeks=1)  # next ISO week's Monday, after today
    raw = _weekly(weeks=9, last_monday=last, weight=100, reps=5, rpe=9.0)
    assert _status(raw) is None


# --- dashboard integration + idempotency -------------------------------------


def test_render_dashboard_includes_callout_when_triggered() -> None:
    raw = _weekly(weeks=9, last_monday=date(2026, 6, 8), weight=100, reps=5)
    records = build_records(raw)
    histories = exercise_histories(records)
    out = render_dashboard(
        records, histories, {}, {}, TODAY, deload_weeks=6, deload_rpe=8.5
    )
    assert "> [!note] Deload readiness" in out
    assert _LABEL in out


def test_render_dashboard_silent_by_default() -> None:
    # deload_weeks defaults to 0 (no-op) -> the section never appears unless the
    # build threads the real config value.
    raw = _weekly(weeks=9, last_monday=date(2026, 6, 8), weight=100, reps=5, rpe=9.0)
    records = build_records(raw)
    histories = exercise_histories(records)
    out = render_dashboard(records, histories, {}, {}, TODAY)
    assert "Deload readiness" not in out


def test_render_dashboard_is_idempotent_when_firing() -> None:
    raw = _weekly(weeks=9, last_monday=date(2026, 6, 8), weight=100, reps=5)
    records = build_records(raw)
    histories = exercise_histories(records)
    first = render_dashboard(
        records, histories, {}, {}, TODAY, deload_weeks=6, deload_rpe=8.5
    )
    second = render_dashboard(
        records, histories, {}, {}, TODAY, deload_weeks=6, deload_rpe=8.5
    )
    assert first == second
    assert "Deload readiness" in first
