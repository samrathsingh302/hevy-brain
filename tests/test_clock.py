"""Tests for the Europe/London civil-day clock.

The bug these guard against: a session logged just after local midnight during
British Summer Time (00:30 BST == 23:30 UTC) used to be dated to the *previous*
day, because "today" was computed from the UTC calendar day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from hevy_brain import clock


def test_london_zone_key() -> None:
    assert clock.LONDON.key == "Europe/London"


def test_civil_day_bst_evening_is_same_day() -> None:
    # 21:00 UTC in July == 22:00 BST, still the 1st.
    instant = datetime(2026, 7, 1, 21, 0, tzinfo=UTC)
    assert clock.civil_day(instant) == date(2026, 7, 1)


def test_civil_day_bst_after_local_midnight_rolls_forward() -> None:
    # 23:30 UTC in July == 00:30 BST the *next* day. The headline regression:
    # the naive UTC .date() would wrongly report the 1st.
    instant = datetime(2026, 7, 1, 23, 30, tzinfo=UTC)
    assert instant.date() == date(2026, 7, 1)  # the old, wrong answer
    assert clock.civil_day(instant) == date(2026, 7, 2)  # the corrected one


def test_civil_day_bst_just_before_local_midnight_is_same_day() -> None:
    # 22:30 UTC in July == 23:30 BST, still the 1st.
    instant = datetime(2026, 7, 1, 22, 30, tzinfo=UTC)
    assert clock.civil_day(instant) == date(2026, 7, 1)


def test_civil_day_gmt_winter_matches_utc() -> None:
    # In January London is on GMT (== UTC), so the civil day matches outright.
    instant = datetime(2026, 1, 15, 23, 30, tzinfo=UTC)
    assert clock.civil_day(instant) == date(2026, 1, 15)


def test_civil_day_naive_is_treated_as_utc() -> None:
    # The cache stores Hevy timestamps as UTC; a naive value must behave the
    # same as the equivalent UTC-aware one.
    naive = datetime(2026, 7, 1, 23, 30)  # noqa: DTZ001 — naive-as-UTC under test
    aware = datetime(2026, 7, 1, 23, 30, tzinfo=UTC)
    assert clock.civil_day(naive) == clock.civil_day(aware) == date(2026, 7, 2)


def test_civil_day_converts_from_a_non_utc_offset() -> None:
    # 01:00 at +02:00 == 23:00 UTC (30 June) == 00:00 BST (1 July).
    instant = datetime(2026, 7, 1, 1, 0, tzinfo=timezone(timedelta(hours=2)))
    assert clock.civil_day(instant) == date(2026, 7, 1)


def test_to_london_preserves_the_instant_in_local_hours() -> None:
    # 21:18 UTC in April == 22:18 +01:00 — same instant, London wall-clock.
    aware = datetime(2026, 4, 11, 21, 18, tzinfo=UTC)
    london = clock.to_london(aware)
    assert london.tzinfo is clock.LONDON
    assert (london.hour, london.minute) == (22, 18)
    assert london == aware  # same instant, only the representation differs


def test_to_london_treats_naive_as_utc() -> None:
    naive = datetime(2026, 7, 1, 23, 30)  # noqa: DTZ001 — naive-as-UTC under test
    assert clock.to_london(naive).date() == date(2026, 7, 2)


def test_civil_day_delegates_to_to_london() -> None:
    instant = datetime(2026, 7, 1, 23, 30, tzinfo=UTC)
    assert clock.civil_day(instant) == clock.to_london(instant).date()


def test_now_london_is_london_aware() -> None:
    now = clock.now_london()
    assert now.tzinfo is clock.LONDON


def test_today_london_returns_a_date_near_utc_today() -> None:
    today = clock.today_london()
    assert isinstance(today, date)
    utc_today = datetime.now(tz=UTC).date()
    # London is at most one civil day off UTC.
    assert abs((today - utc_today).days) <= 1
