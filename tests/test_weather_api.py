from datetime import datetime, timedelta, timezone

import pytest

from workhours.web import create_app


@pytest.fixture()
def app(tmp_path):
    now = datetime(2026, 9, 9, 8, tzinfo=timezone(timedelta(hours=8)))
    app = create_app(tmp_path / 'weather-api.db', lambda: now.date(), lambda: now.replace(tzinfo=None))
    app.config.update(TESTING=True, HOLIDAY_NETWORK_ENABLED=False,
                      WEATHER_NOW_PROVIDER=lambda: now, WEATHER_NETWORK_ENABLED=True)
    return app


def forecast():
    return {
        'timezone': 'Asia/Shanghai',
        'daily': {
            'time': [f'2026-09-{day:02d}' for day in range(9, 16)],
            'weather_code': [0, 2, 3, 61, 95, 45, 1],
            'temperature_2m_min': [20, 21, 22, 18, 19, 21, 22],
            'temperature_2m_max': [28, 29, 30, 26, 27, 29, 30],
        },
    }


def test_weather_is_a_separate_endpoint_and_does_not_change_workhours(app):
    client = app.test_client()
    client.put('/api/entries/2026-09-09', json={'start_time': '08:00', 'end_time': None})
    calls = []
    app.config['WEATHER_FETCHER'] = lambda url: (calls.append(url), forecast())[1]
    before = client.get('/api/dashboard').json
    assert calls == []
    response = client.get('/api/weather?month=2026-09')
    assert response.status_code == 200
    data = response.json
    assert data['city'] == '杭州' and data['timezone'] == 'Asia/Shanghai'
    assert data['month'] == '2026-09' and data['source'] == 'remote'
    assert data['forecast_start'] == '2026-09-09' and data['forecast_end'] == '2026-09-15'
    assert len(data['days']) == 7 and data['days']['2026-09-09']['temperature_min'] == 20
    assert data['days']['2026-09-09']['temperature_max'] == 28
    assert len(calls) == 1
    assert client.get('/api/dashboard').json == before
    assert client.get('/api/weather?month=2026-09').json['source'] == 'cache'
    assert len(calls) == 1


@pytest.mark.parametrize('query', ['', '?month=2026-13', '?month=2026-9', '?month=invalid'])
def test_weather_rejects_invalid_month_without_network(app, query):
    def forbidden(url):
        raise AssertionError('Invalid query must not call the weather provider')
    app.config['WEATHER_FETCHER'] = forbidden
    response = app.test_client().get('/api/weather' + query)
    assert response.status_code == 400
    assert response.json['error']


def test_weather_unavailable_does_not_block_punches_or_preview(app):
    app.config['WEATHER_FETCHER'] = lambda url: (_ for _ in ()).throw(OSError('offline'))
    client = app.test_client()
    weather = client.get('/api/weather?month=2026-09')
    assert weather.status_code == 200
    assert weather.json['days'] == {} and weather.json['source'] == 'unavailable'
    assert client.put('/api/entries/2026-09-09', json={'start_time': '08:00', 'end_time': None}).status_code == 200
    assert client.get('/api/dashboard').json['selected_preview']['suggested_end'] == '18:30'


def test_weather_outside_forecast_month_never_fetches(app):
    app.config['WEATHER_FETCHER'] = lambda url: (_ for _ in ()).throw(AssertionError('Unexpected weather request'))
    result = app.test_client().get('/api/weather?month=2026-08')
    assert result.status_code == 200 and result.json['days'] == {}
    assert result.json['source'] == 'unavailable'
