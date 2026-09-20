from datetime import date, datetime, time

import pytest

from workhours.domain import DayOverride, PeriodMode, WorkEntry
from workhours.web import create_app


@pytest.fixture()
def app(tmp_path):
    app = create_app(tmp_path / 'remaining.db', lambda: date(2026, 9, 20),
                     lambda: datetime(2026, 9, 20, 8))
    app.config.update(TESTING=True, HOLIDAY_NETWORK_ENABLED=False, WEATHER_NETWORK_ENABLED=False)
    store = app.extensions['workhours_store']
    store.set_period(PeriodMode.MONTH)
    # 用于复现用户报告的 22 个工作日、14 天实录和 23 分钟盈余。
    store.set_override(date(2026, 9, 20), DayOverride.WORKDAY)
    store.set_override(date(2026, 9, 25), DayOverride.HOLIDAY)
    for day in range(1, 20):
        work_date = date(2026, 9, day)
        if work_date.weekday() < 5:
            store.save_entry(WorkEntry(work_date, time(8), time(18, 53 if day == 1 else 30)))
    return app


def dashboard(client, day):
    response = client.get(f'/api/dashboard?reference_date=2026-09-{day:02d}')
    assert response.status_code == 200
    return response.json


def test_month_remaining_uses_actual_hours_for_every_selected_date(app):
    client = app.test_client()
    for day in range(1, 31):
        data = dashboard(client, day)
        for totals in (data['month'], data['forecast']):
            assert totals['target_minutes'] == 198 * 60
            assert totals['completed_minutes'] == 126 * 60 + 23
            assert totals['remaining_target_minutes'] == 71 * 60 + 37
        assert data['forecast']['goal_met'] is False
    # 提醒仍独立保留，缺录天数不再抵扣统计行中的待完成。
    assert dashboard(client, 20)['month']['missing_history_days'] == []
    assert dashboard(client, 24)['month']['missing_history_days'] == [
        '2026-09-20', '2026-09-21', '2026-09-22', '2026-09-23',
    ]


def test_same_week_remaining_stays_fixed_with_existing_carryover(app):
    client = app.test_client()
    assert client.put('/api/settings', json={'period': 'week'}).status_code == 200
    for day in range(21, 28):
        data = dashboard(client, day)
        period = data['forecast']
        assert (period['period_start'], period['period_end']) == ('2026-09-21', '2026-09-27')
        assert period['carryover_minutes'] == -23
        assert period['target_minutes'] == 36 * 60 - 23
        assert period['completed_minutes'] == 0
        assert period['remaining_target_minutes'] == period['target_minutes']
        assert period['goal_met'] is False
        assert data['month']['remaining_target_minutes'] == 71 * 60 + 37


def test_punches_leave_and_calendar_changes_recompute_actual_remaining(app):
    client = app.test_client()
    # 仅上班的记录没有有效工时，不能按 9 小时抵扣。
    assert client.put('/api/entries/2026-09-20', json={'start_time': '08:00', 'end_time': None}).status_code == 200
    partial = dashboard(client, 24)
    assert partial['forecast']['remaining_target_minutes'] == 71 * 60 + 37
    assert '2026-09-20' in partial['month']['missing_history_days']

    assert client.put('/api/entries/2026-09-20', json={'start_time': '08:00', 'end_time': '18:30'}).status_code == 200
    complete = dashboard(client, 24)
    assert complete['forecast']['completed_minutes'] == 135 * 60 + 23
    assert complete['forecast']['remaining_target_minutes'] == 62 * 60 + 37
    assert '2026-09-20' not in complete['month']['missing_history_days']

    assert client.put('/api/leaves/2026-09-22', json={'enabled': True}).status_code == 200
    leave = dashboard(client, 24)
    assert leave['forecast']['target_minutes'] == 189 * 60
    assert leave['forecast']['remaining_target_minutes'] == 53 * 60 + 37
    assert '2026-09-22' not in leave['month']['missing_history_days']

    assert client.put('/api/calendar/2026-09-23', json={'kind': 'holiday'}).status_code == 200
    holiday = dashboard(client, 24)
    assert holiday['forecast']['target_minutes'] == 180 * 60
    assert holiday['forecast']['remaining_target_minutes'] == 44 * 60 + 37
    assert client.delete('/api/entries/2026-09-20').status_code == 200
    assert dashboard(client, 24)['forecast']['remaining_target_minutes'] == 53 * 60 + 37


def test_missing_history_cannot_mark_actual_target_as_completed(app):
    store = app.extensions['workhours_store']
    for day in list(store.list_entries(date(2026, 9, 1), date(2026, 9, 30))):
        store.delete_entry(day)
    store.save_entry(WorkEntry(date(2026, 9, 30), time(8), time(18, 30)))
    data = dashboard(app.test_client(), 30)
    assert data['forecast']['completed_minutes'] == 9 * 60
    assert data['forecast']['remaining_target_minutes'] == 189 * 60
    assert data['forecast']['goal_met'] is False
    assert len(data['month']['missing_history_days']) == 21


def test_actual_remaining_is_zero_after_recorded_hours_exceed_target(app):
    store = app.extensions['workhours_store']
    for day in range(1, 31):
        work_date = date(2026, 9, day)
        if (work_date.weekday() < 5 and day != 25) or day == 20:
            store.save_entry(WorkEntry(work_date, time(8), time(19 if day == 1 else 18, 0 if day == 1 else 30)))
    client = app.test_client()
    for selected in (1, 20, 24, 30):
        data = dashboard(client, selected)
        assert data['forecast']['target_minutes'] == 198 * 60
        assert data['forecast']['completed_minutes'] == 198 * 60 + 30
        assert data['forecast']['remaining_target_minutes'] == data['month']['remaining_target_minutes'] == 0
        assert data['forecast']['goal_met'] is True
