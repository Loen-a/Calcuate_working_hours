from datetime import date, time

from workhours.domain import (
    ForecastSettings,
    NonWorkingInterval,
    PeriodMode,
    WorkEntry,
    build_forecast,
    default_non_working_intervals,
    effective_minutes,
)


DEFAULT_RULES = default_non_working_intervals()


def test_effective_minutes_deducts_only_overlapping_default_intervals():
    entry = WorkEntry(date(2026, 7, 15), time(9), time(20, 30))

    assert effective_minutes(entry, DEFAULT_RULES) == 9 * 60 + 30


def test_effective_minutes_deducts_partial_interval_overlap():
    entry = WorkEntry(date(2026, 7, 15), time(13, 30), time(19, 45))

    assert effective_minutes(entry, DEFAULT_RULES) == 6 * 60


def test_effective_minutes_counts_time_after_evening_break():
    entry = WorkEntry(date(2026, 7, 15), time(20), time(21))

    assert effective_minutes(entry, DEFAULT_RULES) == 60


def test_overlapping_intervals_are_deducted_once():
    rules = (
        NonWorkingInterval(None, "Lunch", time(12), time(13, 30)),
        NonWorkingInterval(None, "Extended break", time(13), time(14)),
    )
    entry = WorkEntry(date(2026, 7, 15), time(11), time(15))

    assert effective_minutes(entry, rules) == 2 * 60


def test_disabled_intervals_do_not_reduce_effective_time():
    rules = (
        NonWorkingInterval(None, "Disabled", time(12), time(13), False),
    )
    entry = WorkEntry(date(2026, 7, 15), time(11), time(14))

    assert effective_minutes(entry, rules) == 3 * 60


def test_recurring_intervals_apply_to_overnight_entry():
    entry = WorkEntry(date(2026, 7, 15), time(23), time(13))

    assert effective_minutes(entry, DEFAULT_RULES) == 13 * 60


def test_suggested_end_skips_lunch_and_evening_break():
    entries = {
        date(2026, 7, day): WorkEntry(
            date(2026, 7, day),
            time(9),
            time(19, 15),
        )
        for day in (6, 7, 8, 9)
    }
    entries[date(2026, 7, 10)] = WorkEntry(
        date(2026, 7, 10),
        time(9),
        None,
    )

    forecast = build_forecast(
        reference_date=date(2026, 7, 10),
        entries=entries,
        overrides={},
        settings=ForecastSettings(
            period=PeriodMode.WEEK,
            non_working_intervals=DEFAULT_RULES,
        ),
    )

    assert forecast.days[date(2026, 7, 10)].recommended_minutes == 10 * 60
    assert forecast.days[date(2026, 7, 10)].suggested_end == time(21)
