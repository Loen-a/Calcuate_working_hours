from datetime import date, time

import pytest

from workhours.domain import DayOverride, WorkEntry
from workhours.web import create_app


@pytest.fixture()
def app(tmp_path):
    app = create_app(tmp_path / 'averages.db', lambda: date(2026, 9, 29))
    app.config.update(TESTING=True, HOLIDAY_NETWORK_ENABLED=False, WEATHER_NETWORK_ENABLED=False)
    return app


def save(app, day, start=time(8), end=time(18)):
    app.extensions['workhours_store'].save_entry(WorkEntry(date.fromisoformat(day), start, end))


def averages(app, selected='2026-09-29'):
    response = app.test_client().get('/api/dashboard', query_string={'reference_date': selected})
    assert response.status_code == 200
    return response.json['averages']


def test_history_is_weighted_by_recorded_days_and_month_ignores_selected_day(app):
    save(app, '2025-12-31')  # 8.5h
    save(app, '2026-09-01', end=time(18, 30))  # 9h
    save(app, '2026-09-02', end=time(19))  # 9.5h
    for selected in ('2026-09-01', '2026-09-29', '2026-09-30'):
        assert averages(app, selected) == {'all_time_minutes': 540, 'month_minutes': 555}
    assert averages(app, '2025-12-31') == {'all_time_minutes': 540, 'month_minutes': 510}
    assert averages(app, '2026-08-01') == {'all_time_minutes': 540, 'month_minutes': None}


def test_missing_partial_rest_and_leave_do_not_dilute_averages(app):
    store = app.extensions['workhours_store']
    save(app, '2026-09-01', end=None)
    save(app, '2026-09-02', start=None)
    save(app, '2026-09-03')
    store.set_leave(date(2026, 9, 3), True)
    save(app, '2026-09-04')
    store.set_override(date(2026, 9, 4), DayOverride.HOLIDAY)
    save(app, '2026-09-05')  # Saturday
    save(app, '2026-09-06')
    store.set_override(date(2026, 9, 6), DayOverride.WORKDAY)
    assert averages(app) == {'all_time_minutes': 510, 'month_minutes': 510}
    # A complete zero-duration entry is a recorded day, just as in the completed card.
    save(app, '2026-09-07', end=time(8))
    assert averages(app) == {'all_time_minutes': 255, 'month_minutes': 255}
    app.test_client().delete('/api/entries/2026-09-07')
    assert averages(app) == {'all_time_minutes': 510, 'month_minutes': 510}


def test_historical_calendars_apply_automatic_makeup_and_manual_priority(app):
    calls = []

    def fetch(url):
        year = int(url.rsplit('/', 1)[-1].split('.')[0])
        calls.append(year)
        return {'days': [
            {'date': f'{year}-12-27' if year == 2025 else f'{year}-09-05',
             'name': '调休上班', 'isOffDay': False},
            {'date': f'{year}-12-29' if year == 2025 else f'{year}-09-01',
             'name': '放假', 'isOffDay': True},
        ]}

    app.config.update(HOLIDAY_NETWORK_ENABLED=True, HOLIDAY_FETCHER=fetch)
    store = app.extensions['workhours_store']
    save(app, '2025-12-27')
    save(app, '2025-12-29', end=time(19))
    store.set_override(date(2025, 12, 29), DayOverride.WORKDAY)
    save(app, '2026-09-01')
    save(app, '2026-09-02', end=time(18, 30))
    save(app, '2026-09-05')
    store.set_override(date(2026, 9, 5), DayOverride.HOLIDAY)
    assert averages(app) == {'all_time_minutes': 540, 'month_minutes': 540}
    assert sorted(calls) == [2025, 2026]
    assert averages(app, '2025-12-31') == {'all_time_minutes': 540, 'month_minutes': 540}
    assert sorted(calls) == [2025, 2026]  # both years now use the existing cache


def test_rule_changes_recompute_history_and_overnight_entries(app):
    save(app, '2025-12-31', start=time(22), end=time(7))  # 9h, overnight
    save(app, '2026-09-01', end=time(18, 30))  # 9h after lunch
    assert averages(app) == {'all_time_minutes': 540, 'month_minutes': 540}
    client = app.test_client()
    lunch = next(i for i in client.get('/api/dashboard').json['intervals'] if i['name'] == '午休')
    lunch['enabled'] = False
    assert client.post('/api/non-working-intervals', json=lunch).status_code == 200
    assert averages(app) == {'all_time_minutes': 585, 'month_minutes': 630}
    assert client.put('/api/leaves/2025-12-31', json={'enabled': True}).status_code == 200
    assert averages(app) == {'all_time_minutes': 630, 'month_minutes': 630}


def test_no_complete_records_returns_null_instead_of_zero(app):
    assert averages(app) == {'all_time_minutes': None, 'month_minutes': None}
    save(app, '2026-09-01', end=None)
    assert averages(app) == {'all_time_minutes': None, 'month_minutes': None}


def test_month_average_keeps_fractional_minutes_until_display(app):
    store = app.extensions['workhours_store']
    for day in range(1, 21):
        work_date = date(2026, 9, day)
        store.set_override(work_date, DayOverride.WORKDAY)
        save(app, work_date.isoformat(), end=time(18, 45 if day == 1 else 30))
    assert averages(app) == {'all_time_minutes': 540.75, 'month_minutes': 540.75}
