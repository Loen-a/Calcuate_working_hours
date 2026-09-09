from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from workhours.air_quality import CACHE_KEY, get_air_quality
from workhours.backup import build_backup
from workhours.storage import WorkHoursStore

NOW = datetime(2026, 9, 9, 9)


def payload(start=NOW):
    midnight = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return {'timezone': 'Asia/Shanghai', 'utc_offset_seconds': 28800,
            'hourly_units': {'us_aqi': 'USAQI'},
            'hourly': {'time': [(midnight + timedelta(hours=i)).isoformat(timespec='minutes') for i in range(168)],
                       'us_aqi': [35] * 120 + [None] * 48}}


@pytest.fixture()
def store(tmp_path):
    return WorkHoursStore(tmp_path / 'air.db')


def offline(_url):
    raise OSError('offline')


def test_air_quality_uses_complete_local_days_and_does_not_enter_business_backup(store):
    raw = payload()
    raw['hourly']['us_aqi'][23] = 86
    raw['hourly']['us_aqi'][119] = None  # A partial fifth day cannot claim a daily maximum.
    calls = []
    before = build_backup(store)
    result = get_air_quality(store, NOW.date(), now=NOW, fetcher=lambda url: (calls.append(url), raw)[1])
    assert result.standard == 'US' and result.source == 'remote'
    assert result.timezone == 'Asia/Shanghai' and result.forecast_start == '2026-09-09'
    assert len(result.days) == 4 and result.days['2026-09-09'] == {'aqi_max': 86, 'category': 'moderate', 'label': '中等'}
    assert '2026-09-13' not in result.days and '2026-09-15' not in result.days
    query = parse_qs(urlparse(calls[0]).query)
    assert query['hourly'] == ['us_aqi'] and query['timezone'] == ['Asia/Shanghai'] and query['forecast_days'] == ['7']
    assert get_air_quality(store, NOW.date(), now=NOW + timedelta(minutes=59), fetcher=offline).days == result.days
    assert get_air_quality(store, NOW.date(), now=NOW + timedelta(hours=1), fetcher=offline).stale
    after = build_backup(store)
    before.pop('exportedAt'); after.pop('exportedAt')
    assert before == after


@pytest.mark.parametrize('value,category', [(0, 'good'), (50, 'good'), (51, 'moderate'), (100, 'moderate'),
    (101, 'sensitive'), (150, 'sensitive'), (151, 'unhealthy'), (200, 'unhealthy'),
    (201, 'very-unhealthy'), (300, 'very-unhealthy'), (301, 'hazardous'), (510, 'hazardous')])
def test_us_aqi_categories(store, value, category):
    raw = payload()
    raw['hourly']['us_aqi'] = [value] * 168
    result = get_air_quality(store, NOW.date(), now=NOW, fetcher=lambda url: raw)
    assert result.days['2026-09-09']['category'] == category


@pytest.mark.parametrize('value', [None, -1, True, '40', float('nan'), float('inf')])
def test_missing_or_invalid_hour_excludes_only_its_day(store, value):
    raw = payload()
    raw['hourly']['us_aqi'][10] = value
    result = get_air_quality(store, NOW.date(), now=NOW, fetcher=lambda url: raw)
    assert '2026-09-09' not in result.days and len(result.days) == 4


def test_midnight_invalidates_cache_and_offline_response_excludes_yesterday(store):
    first = get_air_quality(store, NOW.date(), now=datetime(2026, 9, 9, 23, 50), fetcher=lambda url: payload())
    after_midnight = datetime(2026, 9, 9, 16, 10, tzinfo=timezone.utc)
    result = get_air_quality(store, NOW.date(), now=after_midnight, fetcher=offline)
    assert result.stale and result.fetched_at == first.fetched_at
    assert result.forecast_start == '2026-09-10' and '2026-09-09' not in result.days
    assert get_air_quality(store, NOW.date(), now=NOW + timedelta(days=7), fetcher=offline).days == {}


@pytest.mark.parametrize('damage', ['timezone', 'units', 'dates', 'all-null'])
def test_bad_or_empty_air_response_never_replaces_valid_cache(store, damage):
    get_air_quality(store, NOW.date(), now=NOW, fetcher=lambda url: payload())
    original = store.get_weather_cache(CACHE_KEY)
    raw = payload()
    if damage == 'timezone': raw['timezone'] = 'UTC'
    if damage == 'units': raw['hourly_units']['us_aqi'] = 'European AQI'
    if damage == 'dates': raw['hourly']['time'][1] = raw['hourly']['time'][0]
    if damage == 'all-null': raw['hourly']['us_aqi'] = [None] * 168
    result = get_air_quality(store, NOW.date(), now=NOW + timedelta(hours=2), fetcher=lambda url: raw)
    assert result.stale and store.get_weather_cache(CACHE_KEY) == original


def test_unrelated_month_and_network_disabled_never_fetch(store):
    forbidden = lambda url: pytest.fail('unexpected network request')
    assert get_air_quality(store, NOW.date().replace(month=8), now=NOW, fetcher=forbidden).days == {}
    assert get_air_quality(store, NOW.date(), now=NOW, allow_network=False, fetcher=forbidden).days == {}
