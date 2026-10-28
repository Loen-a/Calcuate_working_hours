from dataclasses import replace
from datetime import date, datetime, time

import pytest

from workhours.backup import InvalidBackup, build_backup, restore_backup
from workhours.domain import (
    DayOverride, ForecastSettings, WorkEntry, build_forecast,
    default_non_working_intervals, effective_minutes, ends_before_limit,
)
from workhours.storage import WorkHoursStore
from workhours.web import create_app


DAY = date(2026, 10, 27)


@pytest.mark.parametrize('start,end,earliest,expected', [
    ('08:00', '18:00', None, 510),
    ('08:00', '18:00', '08:30', 480),
    ('09:00', '18:00', '08:30', 450),
    ('08:00', '08:15', '08:30', 0),
    ('08:00', '08:00', '08:30', 0),
    ('12:00', '15:00', '13:00', 90),
    ('22:00', '06:00', '08:30', 480),
    ('23:30', '00:30', '23:45', 45),
    ('08:00', '07:00', '08:30', 1230),
    ('22:00', '06:00', '00:00', 480),
])
def test_effective_start_preserves_real_end_date_and_break_deductions(start, end, earliest, expected):
    entry = WorkEntry(DAY, time.fromisoformat(start), time.fromisoformat(end))
    assert effective_minutes(entry, default_non_working_intervals(), time.fromisoformat(earliest) if earliest else None) == expected
    assert entry.start.isoformat(timespec='minutes') == start
    assert entry.end.isoformat(timespec='minutes') == end


@pytest.mark.parametrize('start,start_limit,end_limit,expected,offset', [
    ('07:00', None, None, '16:30', 0),
    ('07:00', None, '17:00', '17:00', 0),
    ('08:00', None, '17:00', '17:30', 0),
    ('07:00', '08:30', '17:00', '18:00', 0),
    ('07:00', '08:30', '19:45', '19:45', 0),
    ('22:00', '08:30', '17:00', '06:00', 1),
    ('23:30', '23:45', '17:00', '07:45', 1),
])
def test_prediction_meets_work_minutes_and_date_aware_time_floor(start, start_limit, end_limit, expected, offset):
    settings = ForecastSettings(target_minutes_per_day=480,
        earliest_start_time=time.fromisoformat(start_limit) if start_limit else None,
        earliest_end_time=time.fromisoformat(end_limit) if end_limit else None)
    entry = WorkEntry(DAY, time.fromisoformat(start))
    forecast = build_forecast(DAY, {DAY: entry}, {}, settings).days[DAY]
    assert forecast.suggested_end == time.fromisoformat(expected)
    assert forecast.suggested_end_day_offset == offset
    assert effective_minutes(replace(entry, end=forecast.suggested_end), settings.non_working_intervals, settings.earliest_start_time) >= 480


@pytest.mark.parametrize('start,end,expected', [
    ('08:00', '16:59', True), ('08:00', '17:00', False),
    ('08:00', '17:01', False), ('22:00', '06:00', False),
    ('08:00', None, False), (None, '16:00', False),
])
def test_early_departure_compares_datetimes_not_only_clock_times(start, end, expected):
    entry = WorkEntry(DAY, time.fromisoformat(start) if start else None, time.fromisoformat(end) if end else None)
    assert ends_before_limit(entry, time(17)) is expected
    assert ends_before_limit(entry, None) is False


@pytest.fixture()
def app(tmp_path):
    app = create_app(tmp_path / 'limits.db', lambda: DAY, lambda: datetime(2026, 10, 27, 16, 30))
    app.config.update(TESTING=True, HOLIDAY_NETWORK_ENABLED=False, WEATHER_NETWORK_ENABLED=False)
    return app


def test_limits_recompute_history_summary_preview_and_flags_without_rewriting_punches(app):
    client = app.test_client()
    store = app.extensions['workhours_store']
    store.save_entry(WorkEntry(date(2025, 12, 31), time(8), time(18)))
    store.save_entry(WorkEntry(DAY, time(7), time(16, 30)))
    before = client.get('/api/dashboard').json
    assert before['month']['completed_minutes'] == 480
    assert before['averages']['all_time_minutes'] == 495
    assert client.put('/api/settings', json={'earliest_start_time': '08:30', 'earliest_end_time': '17:00'}).status_code == 200
    after = client.get('/api/dashboard').json
    day = next(d for d in after['days'] if d['date'] == DAY.isoformat())
    assert after['month']['completed_minutes'] == 390
    assert after['averages'] == {'all_time_minutes': 435, 'month_minutes': 390}
    assert after['month']['balance_minutes'] == before['month']['balance_minutes'] - 90
    assert after['forecast']['completed_minutes'] == 390
    assert after['forecast']['remaining_target_minutes'] == before['forecast']['remaining_target_minutes'] + 90
    assert day['entry'] == {'start_time': '07:00', 'end_time': '16:30'}
    assert day['compliant'] is False and day['before_earliest_end'] is True
    assert after['selected_preview']['suggested_end'] == '19:00'
    reopened = WorkHoursStore(store.database_path).get_settings()
    assert (reopened.earliest_start_time, reopened.earliest_end_time) == (time(8, 30), time(17))
    assert client.put('/api/settings', json={'earliest_start_time': None, 'earliest_end_time': ''}).status_code == 200
    assert client.get('/api/dashboard').json == before


def test_time_floor_is_independent_of_eight_hour_minimum_and_never_invents_work(app):
    client = app.test_client()
    client.put('/api/settings', json={'earliest_end_time': '17:00'})
    client.put('/api/entries/2026-10-27', json={'start_time': '07:00', 'end_time': '16:30'})
    data = client.get('/api/dashboard').json
    day = next(d for d in data['days'] if d['date'] == DAY.isoformat())
    assert day['actual_minutes'] == 480 and day['compliant'] is True
    assert day['before_earliest_end'] is True
    assert data['settings']['earliest_start_time'] is None
    assert client.put('/api/settings', json={'earliest_start_time': '00:00'}).status_code == 200
    assert client.get('/api/dashboard').json['settings']['earliest_start_time'] == '00:00'
    assert client.get('/api/dashboard').json['settings']['earliest_end_time'] == '17:00'


@pytest.mark.parametrize('mode', ['leave', 'rest', 'incomplete', 'overnight'])
def test_no_early_departure_warning_for_excluded_or_next_day_records(app, mode):
    client = app.test_client()
    store = app.extensions['workhours_store']
    client.put('/api/settings', json={'earliest_end_time': '17:00'})
    entry = WorkEntry(DAY, time(22) if mode == 'overnight' else time(8),
                      None if mode == 'incomplete' else time(6) if mode == 'overnight' else time(16))
    store.save_entry(entry)
    if mode == 'leave':
        store.set_leave(DAY, True)
    if mode == 'rest':
        store.set_override(DAY, DayOverride.HOLIDAY)
    day = next(d for d in client.get('/api/dashboard').json['days'] if d['date'] == DAY.isoformat())
    assert day['before_earliest_end'] is False


@pytest.mark.parametrize('bad', ['8:30', '24:00', '08:60', '08:30:00', True, 123, [], {}])
def test_invalid_limit_cannot_partially_update_other_preferences(app, bad):
    client = app.test_client()
    store = app.extensions['workhours_store']
    before = (store.get_settings(), store.get_theme())
    response = client.put('/api/settings', json={'period': 'month', 'theme': 'space',
        'earliest_start_time': '08:30', 'earliest_end_time': bad})
    assert response.status_code == 400
    assert (store.get_settings(), store.get_theme()) == before


def test_backup_round_trip_optional_fields_and_old_v3_reset(app, tmp_path):
    store = app.extensions['workhours_store']
    old_backup = build_backup(store)
    assert set(old_backup['settings']) == {'period', 'theme'}
    app.test_client().put('/api/settings', json={'earliest_start_time': '08:30'})
    store.save_entry(WorkEntry(DAY, time(7), time(17)))
    backup = build_backup(store)
    assert backup['settings']['earliest_start_time'] == '08:30'
    assert backup['settings']['earliest_end_time'] is None
    destination = WorkHoursStore(tmp_path / 'restored.db')
    restore_backup(destination, backup)
    assert destination.get_settings() == store.get_settings()
    assert destination.get_entry(DAY) == store.get_entry(DAY)
    broken = {**backup, 'settings': {**backup['settings'], 'earliest_end_time': '25:00'}}
    with pytest.raises(InvalidBackup):
        restore_backup(destination, broken)
    assert destination.get_settings() == store.get_settings()
    assert destination.get_entry(DAY) == store.get_entry(DAY)
    restore_backup(destination, old_backup)
    assert destination.get_settings().earliest_start_time is None
    assert destination.get_settings().earliest_end_time is None


@pytest.mark.parametrize('version', [1, 2])
def test_legacy_backup_without_limits_preserves_current_limits(app, version):
    app.test_client().put('/api/settings', json={'earliest_start_time': '08:30', 'earliest_end_time': '17:00'})
    store = app.extensions['workhours_store']
    backup = {'version': version, 'exportedAt': '2026-10-27T00:00:00Z', 'entries': {}}
    if version == 2:
        backup.update(preferences={'theme': 'teal'}, holidayCache={})
    restore_backup(store, backup)
    assert (store.get_settings().earliest_start_time, store.get_settings().earliest_end_time) == (time(8, 30), time(17))
