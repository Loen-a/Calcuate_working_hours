from __future__ import annotations

import calendar
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum


class PeriodMode(StrEnum):
    WEEK = "week"
    MONTH = "month"


class DayOverride(StrEnum):
    HOLIDAY = "holiday"
    WORKDAY = "workday"


@dataclass(frozen=True)
class NonWorkingInterval:
    interval_id: int | None
    name: str
    start: time
    end: time
    enabled: bool = True


def default_non_working_intervals() -> tuple[NonWorkingInterval, ...]:
    return (
        NonWorkingInterval(None, "午休", time(12, 0), time(13, 30)),
        NonWorkingInterval(None, "晚间休息", time(19, 30), time(20, 0)),
    )


@dataclass(frozen=True)
class ForecastSettings:
    period: PeriodMode = PeriodMode.WEEK
    target_minutes_per_day: int = 9 * 60
    minimum_minutes_per_day: int = 8 * 60
    lunch_minutes: int = 90
    non_working_intervals: tuple[NonWorkingInterval, ...] = (
        default_non_working_intervals()
    )


@dataclass(frozen=True)
class WorkEntry:
    work_date: date
    start: time | None = None
    end: time | None = None
    lunch_minutes: int | None = None


@dataclass(frozen=True)
class DayForecast:
    work_date: date
    is_workday: bool
    actual_minutes: int | None
    daily_balance_minutes: int | None
    cumulative_balance_minutes: int | None
    balance_before_minutes: int
    required_minutes: int | None
    recommended_minutes: int | None
    suggested_end: time | None
    suggested_end_day_offset: int | None
    reason: str
    compliant: bool | None


@dataclass(frozen=True)
class Forecast:
    period: PeriodMode
    period_start: date
    period_end: date
    workdays: list[date]
    base_target_minutes: int
    carryover_minutes: int
    target_minutes: int
    completed_minutes: int
    remaining_target_minutes: int
    projected_minutes: int
    goal_met: bool
    month_target_minutes: int
    month_completed_minutes: int
    missing_history_days: list[date]
    days: dict[date, DayForecast]


def is_workday(work_date: date, overrides: dict[date, DayOverride]) -> bool:
    override = overrides.get(work_date)
    if override == DayOverride.HOLIDAY:
        return False
    if override == DayOverride.WORKDAY:
        return True
    return work_date.weekday() < 5


def period_bounds(reference_date: date, period: PeriodMode) -> tuple[date, date]:
    month_start, month_end = _month_bounds(reference_date)
    if period == PeriodMode.WEEK:
        week_start = reference_date - timedelta(days=reference_date.weekday())
        week_end = week_start + timedelta(days=6)
        return max(week_start, month_start), min(week_end, month_end)

    return month_start, month_end


def _month_bounds(reference_date: date) -> tuple[date, date]:
    last_day = calendar.monthrange(reference_date.year, reference_date.month)[1]
    return (
        date(reference_date.year, reference_date.month, 1),
        date(reference_date.year, reference_date.month, last_day),
    )


def period_workdays(
    reference_date: date,
    period: PeriodMode,
    overrides: dict[date, DayOverride],
) -> list[date]:
    start, end = period_bounds(reference_date, period)
    days: list[date] = []
    current = start
    while current <= end:
        if is_workday(current, overrides):
            days.append(current)
        current += timedelta(days=1)
    return days


def effective_minutes(
    entry: WorkEntry,
    non_working_intervals: Iterable[NonWorkingInterval],
) -> int | None:
    if entry.start is None or entry.end is None:
        return None

    start_dt = datetime.combine(entry.work_date, entry.start)
    end_dt = datetime.combine(entry.work_date, entry.end)
    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    excluded_minutes = 0
    merged_intervals = _merged_enabled_intervals(non_working_intervals)
    current_date = start_dt.date()
    while current_date <= end_dt.date():
        for interval_start, interval_end in merged_intervals:
            excluded_start = datetime.combine(current_date, interval_start)
            excluded_end = datetime.combine(current_date, interval_end)
            overlap_start = max(start_dt, excluded_start)
            overlap_end = min(end_dt, excluded_end)
            if overlap_end > overlap_start:
                excluded_minutes += int(
                    (overlap_end - overlap_start).total_seconds() // 60
                )
        current_date += timedelta(days=1)

    attendance_minutes = int((end_dt - start_dt).total_seconds() // 60)
    return max(attendance_minutes - excluded_minutes, 0)


def build_forecast(
    reference_date: date,
    entries: dict[date, WorkEntry],
    overrides: dict[date, DayOverride],
    settings: ForecastSettings,
) -> Forecast:
    month_workdays = period_workdays(reference_date, PeriodMode.MONTH, overrides)
    period_start, period_end = period_bounds(reference_date, settings.period)
    workdays = [
        day for day in month_workdays if period_start <= day <= period_end
    ]

    month_target = len(month_workdays) * settings.target_minutes_per_day
    month_completed = _completed_minutes(month_workdays, entries, settings)
    monthly_balances, balances_before_day = _monthly_balances(
        month_workdays,
        entries,
        settings,
    )
    missing_history = [
        day
        for day in month_workdays
        if day < reference_date and _actual_minutes(day, entries, settings) is None
    ]

    base_target = len(workdays) * settings.target_minutes_per_day
    carryover = 0
    if settings.period == PeriodMode.WEEK:
        prior_workdays = [day for day in month_workdays if day < period_start]
        prior_missing = [day for day in missing_history if day < period_start]
        prior_accounted = _completed_minutes(prior_workdays, entries, settings)
        prior_accounted += len(prior_missing) * settings.target_minutes_per_day
        prior_target = len(prior_workdays) * settings.target_minutes_per_day
        carryover = prior_target - prior_accounted
        target_minutes = max(base_target + carryover, 0)
    else:
        target_minutes = month_target

    completed_minutes = _completed_minutes(workdays, entries, settings)
    missing_period_history = [
        day for day in workdays if day in missing_history
    ]
    accounted_minutes = completed_minutes
    accounted_minutes += (
        len(missing_period_history) * settings.target_minutes_per_day
    )
    remaining_target = max(target_minutes - accounted_minutes, 0)
    remaining_days = [
        day
        for day in workdays
        if day >= reference_date
        and _actual_minutes(day, entries, settings) is None
    ]
    goal_met = accounted_minutes >= target_minutes
    recommended = _recommended_minutes(
        remaining_target,
        remaining_days,
        goal_met,
        settings,
    )

    forecasts: dict[date, DayForecast] = {}
    projected_minutes = accounted_minutes

    for day in workdays:
        entry = entries.get(day)
        actual = _actual_minutes(day, entries, settings)
        daily_balance, cumulative_balance = monthly_balances[day]

        if actual is not None:
            forecast = DayForecast(
                work_date=day,
                is_workday=True,
                actual_minutes=actual,
                daily_balance_minutes=daily_balance,
                cumulative_balance_minutes=cumulative_balance,
                balance_before_minutes=balances_before_day[day],
                required_minutes=None,
                recommended_minutes=None,
                suggested_end=None,
                suggested_end_day_offset=None,
                reason="recorded",
                compliant=actual >= settings.minimum_minutes_per_day,
            )
        elif day < reference_date:
            forecast = DayForecast(
                work_date=day,
                is_workday=True,
                actual_minutes=None,
                daily_balance_minutes=daily_balance,
                cumulative_balance_minutes=cumulative_balance,
                balance_before_minutes=balances_before_day[day],
                required_minutes=None,
                recommended_minutes=None,
                suggested_end=None,
                suggested_end_day_offset=None,
                reason="missing_entry",
                compliant=None,
            )
        else:
            recommendation = recommended.get(day, settings.minimum_minutes_per_day)
            projected_minutes += recommendation
            reason = _recommendation_reason(
                remaining_target,
                recommendation,
                goal_met,
                settings,
            )
            required_minutes = max(
                settings.minimum_minutes_per_day,
                settings.target_minutes_per_day - balances_before_day[day],
            )
            suggestion = _suggested_end(entry, required_minutes, settings)
            forecast = DayForecast(
                work_date=day,
                is_workday=True,
                actual_minutes=None,
                daily_balance_minutes=daily_balance,
                cumulative_balance_minutes=cumulative_balance,
                balance_before_minutes=balances_before_day[day],
                required_minutes=required_minutes,
                recommended_minutes=recommendation,
                suggested_end=suggestion[0] if suggestion else None,
                suggested_end_day_offset=suggestion[1] if suggestion else None,
                reason=reason,
                compliant=None,
            )

        forecasts[day] = forecast

    return Forecast(
        period=settings.period,
        period_start=period_start,
        period_end=period_end,
        workdays=workdays,
        base_target_minutes=base_target,
        carryover_minutes=carryover,
        target_minutes=target_minutes,
        completed_minutes=completed_minutes,
        remaining_target_minutes=remaining_target,
        projected_minutes=projected_minutes,
        goal_met=goal_met,
        month_target_minutes=month_target,
        month_completed_minutes=month_completed,
        missing_history_days=missing_history,
        days=forecasts,
    )


def _actual_minutes(
    work_date: date,
    entries: dict[date, WorkEntry],
    settings: ForecastSettings,
) -> int | None:
    entry = entries.get(work_date)
    if entry is None:
        return None
    return effective_minutes(entry, settings.non_working_intervals)


def _completed_minutes(
    workdays: list[date],
    entries: dict[date, WorkEntry],
    settings: ForecastSettings,
) -> int:
    total = 0
    for day in workdays:
        actual = _actual_minutes(day, entries, settings)
        if actual is not None:
            total += actual
    return total


def _monthly_balances(
    workdays: list[date],
    entries: dict[date, WorkEntry],
    settings: ForecastSettings,
) -> tuple[
    dict[date, tuple[int | None, int | None]],
    dict[date, int],
]:
    balances: dict[date, tuple[int | None, int | None]] = {}
    balances_before_day: dict[date, int] = {}
    cumulative = 0
    for day in workdays:
        balances_before_day[day] = cumulative
        actual = _actual_minutes(day, entries, settings)
        if actual is None:
            balances[day] = (None, None)
            continue

        daily = actual - settings.target_minutes_per_day
        cumulative += daily
        balances[day] = (daily, cumulative)
    return balances, balances_before_day


def _recommended_minutes(
    remaining_target: int,
    remaining_days: list[date],
    goal_met: bool,
    settings: ForecastSettings,
) -> dict[date, int]:
    if not remaining_days:
        return {}

    if goal_met:
        return {day: settings.minimum_minutes_per_day for day in remaining_days}

    average_needed = math.ceil(remaining_target / len(remaining_days))
    recommendation = max(settings.minimum_minutes_per_day, average_needed)
    return {day: recommendation for day in remaining_days}


def _recommendation_reason(
    remaining_target: int,
    recommended_minutes: int,
    goal_met: bool,
    settings: ForecastSettings,
) -> str:
    if goal_met:
        return "goal_met_minimum"
    if recommended_minutes == settings.minimum_minutes_per_day:
        return "minimum_day"
    if recommended_minutes == remaining_target:
        return "target_exact"
    return "average_needed"


def _suggested_end(
    entry: WorkEntry | None,
    recommended_minutes: int,
    settings: ForecastSettings,
) -> tuple[time, int] | None:
    if entry is None or entry.start is None:
        return None

    start_dt = datetime.combine(entry.work_date, entry.start)
    end_dt = _advance_work_minutes(
        start_dt,
        recommended_minutes,
        settings.non_working_intervals,
    )
    end_time = end_dt.time().replace(second=0, microsecond=0)
    day_offset = (end_dt.date() - start_dt.date()).days
    return end_time, day_offset


def _merged_enabled_intervals(
    intervals: Iterable[NonWorkingInterval],
) -> tuple[tuple[time, time], ...]:
    enabled = sorted(
        (
            (interval.start, interval.end)
            for interval in intervals
            if interval.enabled and interval.start < interval.end
        ),
        key=lambda item: item[0],
    )
    if not enabled:
        return ()

    merged: list[tuple[time, time]] = [enabled[0]]
    for interval_start, interval_end in enabled[1:]:
        current_start, current_end = merged[-1]
        if interval_start <= current_end:
            merged[-1] = (current_start, max(current_end, interval_end))
        else:
            merged.append((interval_start, interval_end))
    return tuple(merged)


def _advance_work_minutes(
    start_dt: datetime,
    work_minutes: int,
    intervals: Iterable[NonWorkingInterval],
) -> datetime:
    current = start_dt
    remaining = max(work_minutes, 0)
    merged_intervals = _merged_enabled_intervals(intervals)

    while remaining > 0:
        moved_to_interval_end = False
        for interval_start, interval_end in merged_intervals:
            excluded_start = datetime.combine(current.date(), interval_start)
            excluded_end = datetime.combine(current.date(), interval_end)

            if excluded_start <= current < excluded_end:
                current = excluded_end
                moved_to_interval_end = True
                break

            if current < excluded_start:
                available = int(
                    (excluded_start - current).total_seconds() // 60
                )
                if remaining <= available:
                    return current + timedelta(minutes=remaining)
                remaining -= available
                current = excluded_end
                moved_to_interval_end = True
                break

        if moved_to_interval_end:
            continue

        next_day = datetime.combine(current.date() + timedelta(days=1), time())
        available = int((next_day - current).total_seconds() // 60)
        if remaining <= available:
            return current + timedelta(minutes=remaining)
        remaining -= available
        current = next_day

    return current
