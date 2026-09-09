import json
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import pytest

from workhours.backup import build_backup
from workhours.storage import WorkHoursStore
from workhours.weather import LOCATION_KEY, get_weather


NOW = datetime(2026, 9, 9, 9)
TODAY = NOW.date()


def payload(start=TODAY):
    return {
        "timezone": "Asia/Shanghai", "utc_offset_seconds": 28800,
        "daily": {
            "time": [(start + timedelta(days=i)).isoformat() for i in range(7)],
            "weather_code": [0, 2, 3, 45, 51, 61, 95],
            "temperature_2m_min": [20.1] * 7,
            "temperature_2m_max": [29] * 7,
        },
    }


@pytest.fixture
def store(tmp_path):
    return WorkHoursStore(tmp_path / "weather.sqlite3")


def offline(_url):
    raise URLError("offline")


def test_fixed_hangzhou_request_and_normalized_data_persist_outside_business_backup(store):
    calls = []
    def fetch(url):
        calls.append(url)
        return payload()
    before = build_backup(store)
    result = get_weather(store, date(2026, 9, 28), now=NOW, fetcher=fetch)
    assert (result.city, result.timezone, result.month) == ("杭州", "Asia/Shanghai", "2026-09")
    assert (result.forecast_start, result.forecast_end) == ("2026-09-09", "2026-09-15")
    assert result.source == "remote" and not result.stale and result.warning is None
    assert result.fetched_at == "2026-09-09T01:00:00Z"
    assert result.days["2026-09-09"] == {
        "code": 0, "description": "晴", "icon": "clear", "temperature_min": 20.1, "temperature_max": 29,
        "humidity_mean": None,
    }
    parsed = urlparse(calls[0])
    assert parsed.scheme == "https" and parsed.netloc == "api.open-meteo.com"
    query = parse_qs(parsed.query)
    assert query["latitude"] == ["30.29365"] and query["longitude"] == ["120.16142"]
    assert query["timezone"] == ["Asia/Shanghai"] and query["forecast_days"] == ["7"]
    assert set(query["daily"][0].split(",")) == {"weather_code", "temperature_2m_min", "temperature_2m_max", "relative_humidity_2m_mean"}
    reopened = WorkHoursStore(store.database_path)
    assert reopened.get_weather_cache(LOCATION_KEY) == (
        {"forecast_date": TODAY.isoformat(), "days": result.days}, result.fetched_at,
    )
    after = build_backup(reopened)
    before.pop("exportedAt"); after.pop("exportedAt")
    assert after == before


def test_hour_cache_and_expiry_fetch_again_without_holding_a_database_lock(store):
    calls = []
    def fetch(url):
        # A second connection can write while the network request is in progress.
        with store._connect() as connection:
            connection.execute("PRAGMA busy_timeout = 0")
            connection.execute("INSERT OR REPLACE INTO settings VALUES ('weather-test', 'ok')")
        calls.append(url)
        return payload()
    get_weather(store, TODAY, now=NOW, fetcher=fetch)
    assert get_weather(store, TODAY, now=NOW + timedelta(minutes=59), fetcher=fetch).source == "cache"
    assert len(calls) == 1
    assert get_weather(store, TODAY, now=NOW + timedelta(hours=1), fetcher=fetch).source == "remote"
    assert len(calls) == 2


def test_hangzhou_midnight_invalidates_sub_hour_cache_and_cross_month_dates_are_filtered(store):
    before_midnight = datetime(2026, 9, 30, 15, 50, tzinfo=timezone.utc)
    after_midnight = datetime(2026, 9, 30, 16, 10, tzinfo=timezone.utc)
    first = get_weather(store, date(2026, 10, 15), now=before_midnight,
                        fetcher=lambda url: payload(date(2026, 9, 30)))
    assert set(first.days) == {f"2026-10-{i:02d}" for i in range(1, 7)}
    calls = []
    def fetch(url):
        calls.append(url)
        return payload(date(2026, 10, 1))
    second = get_weather(store, date(2026, 10, 15), now=after_midnight, fetcher=fetch)
    assert len(calls) == 1 and second.source == "remote"
    assert second.forecast_start == "2026-10-01" and second.forecast_end == "2026-10-07"
    assert set(second.days) == {f"2026-10-{i:02d}" for i in range(1, 8)}


def test_naive_time_is_hangzhou_and_aware_time_is_converted_before_date_selection(store):
    utc_now = datetime(2026, 9, 8, 16, 1, tzinfo=timezone.utc)
    first = get_weather(store, TODAY, now=utc_now, fetcher=lambda url: payload())
    second = get_weather(store, TODAY, now=datetime(2026, 9, 9, 0, 2), fetcher=offline)
    assert first.forecast_start == second.forecast_start == "2026-09-09"
    assert second.source == "cache" and not second.stale


def test_failed_refresh_filters_yesterday_and_retains_original_cache(store):
    original = get_weather(store, TODAY, now=NOW, fetcher=lambda url: payload())
    cached_before = store.get_weather_cache(LOCATION_KEY)
    result = get_weather(store, TODAY, now=NOW + timedelta(days=1), fetcher=offline)
    assert result.source == "cache" and result.stale and result.warning
    assert result.fetched_at == original.fetched_at
    assert set(result.days) == {f"2026-09-{i:02d}" for i in range(10, 16)}
    assert store.get_weather_cache(LOCATION_KEY) == cached_before
    unavailable = get_weather(store, TODAY, now=NOW + timedelta(days=7), fetcher=offline)
    assert unavailable.source == "unavailable" and unavailable.days == {} and unavailable.warning


@pytest.mark.parametrize("month", [date(2026, 8, 1), date(2026, 10, 31), date(1, 1, 1), date(9999, 12, 1)])
def test_month_outside_current_window_never_requests_weather(store, month):
    result = get_weather(store, month, now=NOW, fetcher=lambda url: pytest.fail("unrelated month fetched"))
    assert result.month == month.isoformat()[:7]
    assert result.source == "unavailable" and result.days == {} and result.warning


def test_network_disabled_uses_relevant_cache_but_does_not_fetch(store):
    fetch = lambda url: pytest.fail("network is disabled")
    assert get_weather(store, TODAY, now=NOW, allow_network=False, fetcher=fetch).source == "unavailable"
    get_weather(store, TODAY, now=NOW, fetcher=lambda url: payload())
    assert get_weather(store, TODAY, now=NOW, allow_network=False, fetcher=fetch).source == "cache"
    stale = get_weather(store, TODAY, now=NOW + timedelta(hours=2), allow_network=False, fetcher=fetch)
    assert stale.source == "cache" and stale.stale and stale.warning


@pytest.mark.parametrize("path,value", [
    (("daily", "time"), [TODAY.isoformat()] * 7),
    (("daily", "time"), [(TODAY + timedelta(days=i + 1)).isoformat() for i in range(7)]),
    (("daily", "time", 0), "2026-9-09"),
    (("daily", "weather_code", 0), 4),
    (("daily", "weather_code", 0), True),
    (("daily", "weather_code", 0), 0.0),
    (("daily", "temperature_2m_min", 0), float("nan")),
    (("daily", "temperature_2m_min", 0), float("inf")),
    (("daily", "temperature_2m_min", 0), True),
    (("daily", "temperature_2m_min", 0), "20"),
    (("daily", "temperature_2m_min", 0), 30),
    (("daily", "temperature_2m_min"), [20] * 6),
    (("daily",), None),
    (("timezone",), "UTC"),
])
def test_bad_upstream_payload_does_not_replace_good_cache(store, path, value):
    get_weather(store, TODAY, now=NOW, fetcher=lambda url: payload())
    before = store.get_weather_cache(LOCATION_KEY)
    bad = payload()
    target = bad
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result = get_weather(store, TODAY, now=NOW + timedelta(hours=2), fetcher=lambda url: bad)
    assert result.source == "cache" and result.stale and result.warning
    assert store.get_weather_cache(LOCATION_KEY) == before


def test_null_day_is_skipped_but_invalid_non_null_data_on_it_is_not_ignored(store):
    raw = payload()
    raw["daily"]["temperature_2m_min"][0] = None
    result = get_weather(store, TODAY, now=NOW, fetcher=lambda url: raw)
    assert result.source == "remote" and len(result.days) == 6
    assert "2026-09-09" not in result.days
    before = store.get_weather_cache(LOCATION_KEY)
    raw["daily"]["weather_code"][0] = 123
    result = get_weather(store, TODAY, now=NOW + timedelta(hours=2), fetcher=lambda url: raw)
    assert result.stale and store.get_weather_cache(LOCATION_KEY) == before


def test_all_null_observations_do_not_replace_a_usable_cache(store):
    get_weather(store, TODAY, now=NOW, fetcher=lambda url: payload())
    before = store.get_weather_cache(LOCATION_KEY)
    raw = payload()
    raw["daily"]["temperature_2m_min"] = [None] * 7
    result = get_weather(store, TODAY, now=NOW + timedelta(hours=2), fetcher=lambda url: raw)
    assert result.source == "cache" and result.stale and len(result.days) == 7
    assert store.get_weather_cache(LOCATION_KEY) == before


def test_future_timestamp_cache_is_ignored_when_clock_moves_back(store):
    get_weather(store, TODAY, now=NOW + timedelta(minutes=20), fetcher=lambda url: payload())
    result = get_weather(store, TODAY, now=NOW, fetcher=offline)
    assert result.source == "unavailable" and result.days == {}


@pytest.mark.parametrize("broken,timestamp", [
    ("{broken", "2026-09-09T01:00:00Z"),
    ("{}", "2026-09-09T01:00:00Z"),
    (json.dumps({"forecast_date": "2026-09-09", "days": {}}), "not-a-time"),
    (json.dumps({"forecast_date": "2026-09-09", "days": {"2026-09-09": {"code": 0}}}), "2026-09-09T01:00:00Z"),
])
def test_corrupt_cache_is_a_miss_and_is_replaced_only_after_successful_fetch(store, broken, timestamp):
    with store._connect() as connection:
        connection.execute("INSERT INTO weather_cache VALUES (?, ?, ?)", (LOCATION_KEY, broken, timestamp))
    result = get_weather(store, TODAY, now=NOW, fetcher=lambda url: payload())
    assert result.source == "remote" and len(result.days) == 7


@pytest.mark.parametrize("code,description,icon", [
    (0, "晴", "clear"), (2, "多云", "partly-cloudy"), (3, "阴", "cloudy"),
    (45, "雾", "fog"), (51, "小毛毛雨", "drizzle"), (61, "小雨", "rain"),
    (71, "小雪", "snow"), (95, "雷暴", "thunderstorm"), (99, "雷暴伴强冰雹", "thunderstorm"),
])
def test_wmo_codes_have_chinese_descriptions_and_supported_icons(store, code, description, icon):
    raw = payload()
    raw["daily"]["weather_code"] = [code] * 7
    result = get_weather(store, TODAY, now=NOW, fetcher=lambda url: raw)
    assert result.days[TODAY.isoformat()]["description"] == description
    assert result.days[TODAY.isoformat()]["icon"] == icon


def test_default_fetcher_uses_five_second_timeout(store, monkeypatch):
    from workhours import weather
    calls = []
    def open_url(url, timeout):
        calls.append((url, timeout))
        return BytesIO(json.dumps(payload()).encode())
    monkeypatch.setattr(weather, "urlopen", open_url)
    assert get_weather(store, TODAY, now=NOW).source == "remote"
    assert calls[0][1] == 5


def test_daily_mean_humidity_is_optional_and_invalid_values_do_not_hide_weather(store):
    raw = payload()
    raw['daily']['relative_humidity_2m_mean'] = [72.4, 0, 100, None, 101, True, '65']
    result = get_weather(store, TODAY, now=NOW, fetcher=lambda url: raw)
    assert len(result.days) == 7
    assert [day['humidity_mean'] for day in result.days.values()] == [72.4, 0, 100, None, None, None, None]
    cached = get_weather(store, TODAY, now=NOW, fetcher=offline)
    assert cached.source == 'cache' and cached.days == result.days


def test_legacy_weather_cache_remains_usable_offline_but_refreshes_to_add_humidity(store):
    original = get_weather(store, TODAY, now=NOW, fetcher=lambda url: payload())
    legacy = {key: {k: v for k, v in value.items() if k != 'humidity_mean'} for key, value in original.days.items()}
    store.set_weather_cache(LOCATION_KEY, {'forecast_date': TODAY.isoformat(), 'days': legacy}, original.fetched_at)
    fallback = get_weather(store, TODAY, now=NOW, fetcher=offline)
    assert fallback.source == 'cache' and fallback.stale and len(fallback.days) == 7
    assert all(day['humidity_mean'] is None for day in fallback.days.values())
    raw = payload()
    raw['daily']['relative_humidity_2m_mean'] = [75] * 7
    updated = get_weather(store, TODAY, now=NOW, fetcher=lambda url: raw)
    assert updated.source == 'remote' and updated.days[TODAY.isoformat()]['humidity_mean'] == 75
