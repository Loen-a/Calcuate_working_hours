import json
from urllib.error import URLError

import pytest

from workhours.holidays import UPSTREAM_URLS, get_holidays
from workhours.storage import WorkHoursStore


def payload():
    return {"days": [
        {"date": "2026-10-01", "name": "国庆节", "isOffDay": True},
        {"date": "2026-10-10", "name": "国庆节", "isOffDay": False},
    ]}


@pytest.fixture
def store(tmp_path):
    return WorkHoursStore(tmp_path / "hours.sqlite3")


def test_fetch_normalizes_holidays_and_compensating_workdays_and_caches(store):
    calls = []

    def fetcher(url):
        calls.append(url)
        return payload()

    result = get_holidays(store, 2026, fetcher=fetcher)
    assert result.source == "remote"
    assert result.warning is None
    assert result.holidays["10-01"]["isOffDay"] is True
    assert result.holidays["10-10"]["isOffDay"] is False
    assert calls == [UPSTREAM_URLS[0].format(year=2026)]
    cached, timestamp = store.get_holiday_cache(2026)
    assert cached == result.holidays
    assert timestamp.endswith("Z")
    assert get_holidays(store, 2026, fetcher=fetcher).source == "cache"
    assert len(calls) == 1


def test_second_source_is_used_after_first_source_fails(store):
    calls = []

    def fetcher(url):
        calls.append(url)
        if len(calls) == 1:
            raise URLError("unavailable")
        return payload()

    assert get_holidays(store, 2026, fetcher=fetcher).source == "remote"
    assert calls == [url.format(year=2026) for url in UPSTREAM_URLS]


def test_refresh_failure_keeps_original_cache_and_warns(store):
    original = {"10-01": {"name": "国庆节", "isOffDay": True}}
    store.set_holiday_cache(2026, original, "2026-01-01T00:00:00Z")

    def offline(url):
        raise URLError("offline")

    result = get_holidays(store, 2026, refresh=True, fetcher=offline)
    assert result.source == "cache"
    assert result.holidays == original
    assert result.warning
    assert store.get_holiday_cache(2026) == (original, "2026-01-01T00:00:00Z")


def test_successful_refresh_replaces_cache(store):
    store.set_holiday_cache(2026, {"01-01": {"name": "元旦", "isOffDay": True}}, "old")
    result = get_holidays(store, 2026, refresh=True, fetcher=lambda url: payload())
    assert result.source == "remote"
    assert "01-01" not in result.holidays
    assert store.get_holiday_cache(2026)[0] == result.holidays


def test_offline_without_cache_does_not_save_empty_calendar(store):
    def offline(url):
        raise URLError("offline")

    result = get_holidays(store, 2026, fetcher=offline)
    assert result.source == "fallback"
    assert result.holidays == {}
    assert result.warning
    assert store.get_holiday_cache(2026) is None


def test_network_can_be_disabled_without_calling_fetcher(store):
    def unexpected(url):
        pytest.fail("network must stay disabled")

    assert get_holidays(store, 2026, allow_network=False, fetcher=unexpected).source == "fallback"
    store.set_holiday_cache(2026, {"10-01": {"name": "国庆节", "isOffDay": True}}, "old")
    assert get_holidays(store, 2026, allow_network=False, fetcher=unexpected).source == "cache"


@pytest.mark.parametrize("raw", [
    {},
    {"days": []},
    {"days": [None]},
    {"days": [{"date": "2025-10-01", "name": "holiday", "isOffDay": True}]},
    {"days": [{"date": "2026-2-1", "name": "holiday", "isOffDay": True}]},
    {"days": [{"date": "2026-10-01", "name": "holiday", "isOffDay": 1}]},
    {"days": [{"date": "2026-10-01", "name": "holiday", "isOffDay": True}] * 2},
])
def test_invalid_upstream_data_is_not_cached(store, raw):
    result = get_holidays(store, 2026, fetcher=lambda url: raw)
    assert result.source == "fallback"
    assert store.get_holiday_cache(2026) is None


@pytest.mark.parametrize("year", [1999, 2101, True, "2026"])
def test_invalid_year_is_rejected_before_network(store, year):
    with pytest.raises(ValueError, match="2000"):
        get_holidays(store, year, fetcher=lambda url: pytest.fail("invalid year fetched"))


def test_default_fetcher_uses_urllib_timeout_and_environment_proxy_behavior(store, monkeypatch):
    from io import BytesIO
    from workhours import holidays

    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        return BytesIO(json.dumps(payload()).encode())

    monkeypatch.setattr(holidays, "urlopen", fake_urlopen)
    result = get_holidays(store, 2026)
    assert result.source == "remote"
    assert calls == [(UPSTREAM_URLS[0].format(year=2026), 5)]
