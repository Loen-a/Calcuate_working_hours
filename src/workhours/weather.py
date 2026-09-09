"""Independent, cached seven-day weather for Hangzhou; no attendance decisions."""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from http.client import HTTPException
from typing import Literal
from urllib.parse import urlencode
from urllib.request import urlopen

from workhours.storage import WorkHoursStore


LOCATION_KEY = "hangzhou"
CITY = "杭州"
TIMEZONE = "Asia/Shanghai"
HANGZHOU_TZ = timezone(timedelta(hours=8))
FORECAST_URL = "https://api.open-meteo.com/v1/forecast?" + urlencode({
    "latitude": "30.29365", "longitude": "120.16142",
    "daily": "weather_code,temperature_2m_min,temperature_2m_max",
    "forecast_days": 7, "timezone": TIMEZONE, "temperature_unit": "celsius",
})

# Open-Meteo WMO interpretation codes: https://open-meteo.com/en/docs
_CONDITIONS = {
    0: ("晴", "clear"), 1: ("晴间多云", "partly-cloudy"),
    2: ("多云", "partly-cloudy"), 3: ("阴", "cloudy"),
    45: ("雾", "fog"), 48: ("雾凇", "fog"),
    51: ("小毛毛雨", "drizzle"), 53: ("中等毛毛雨", "drizzle"), 55: ("强毛毛雨", "drizzle"),
    56: ("轻微冻毛毛雨", "drizzle"), 57: ("强冻毛毛雨", "drizzle"),
    61: ("小雨", "rain"), 63: ("中雨", "rain"), 65: ("大雨", "rain"),
    66: ("轻微冻雨", "rain"), 67: ("强冻雨", "rain"),
    71: ("小雪", "snow"), 73: ("中雪", "snow"), 75: ("大雪", "snow"), 77: ("雪粒", "snow"),
    80: ("小阵雨", "rain"), 81: ("中等阵雨", "rain"), 82: ("强阵雨", "rain"),
    85: ("小阵雪", "snow"), 86: ("大阵雪", "snow"),
    95: ("雷暴", "thunderstorm"), 96: ("雷暴伴冰雹", "thunderstorm"),
    99: ("雷暴伴强冰雹", "thunderstorm"),
}

WeatherDays = dict[str, dict[str, str | int | float]]


@dataclass(frozen=True)
class WeatherResult:
    city: str
    timezone: str
    month: str
    forecast_start: str
    forecast_end: str
    source: Literal["remote", "cache", "unavailable"]
    stale: bool
    fetched_at: str | None
    warning: str | None
    days: WeatherDays


def _parse_date(raw: object) -> date:
    if not isinstance(raw, str):
        raise ValueError("天气日期必须是字符串。")
    parsed = date.fromisoformat(raw)
    if parsed.isoformat() != raw:
        raise ValueError("天气日期格式无效。")
    return parsed


def _number(raw: object) -> int | float:
    if type(raw) not in (int, float):
        raise ValueError("天气温度必须是有限数字。")
    try:
        finite = math.isfinite(raw)
    except OverflowError as exc:
        raise ValueError("天气温度超出有效范围。") from exc
    if not finite:
        raise ValueError("天气温度必须是有限数字。")
    return raw


def _day(code: object, low: object, high: object) -> dict | None:
    # Validate non-null values even when another observation is missing.
    if code is not None and (type(code) is not int or code not in _CONDITIONS):
        raise ValueError("天气代码不受支持。")
    if low is not None:
        _number(low)
    if high is not None:
        _number(high)
    if low is not None and high is not None and low > high:
        raise ValueError("最低温度不能高于最高温度。")
    if code is None or low is None or high is None:
        return None
    description, icon = _CONDITIONS[code]
    return {"code": code, "description": description, "icon": icon,
            "temperature_min": low, "temperature_max": high}


def _normalize(raw: object, forecast_date: date) -> WeatherDays:
    if not isinstance(raw, dict) or not isinstance(raw.get("daily"), dict):
        raise ValueError("天气响应缺少 daily 数据。")
    if raw.get("timezone", TIMEZONE) != TIMEZONE or raw.get("utc_offset_seconds", 28800) != 28800:
        raise ValueError("天气响应时区不是杭州时间。")
    units = raw.get("daily_units", {})
    if not isinstance(units, dict) or any(
        units.get(key, "°C") != "°C"
        for key in ("temperature_2m_min", "temperature_2m_max")
    ):
        raise ValueError("天气响应温度单位不是摄氏度。")
    daily = raw["daily"]
    keys = ("time", "weather_code", "temperature_2m_min", "temperature_2m_max")
    if any(not isinstance(daily.get(key), list) or len(daily[key]) != 7 for key in keys):
        raise ValueError("天气响应必须包含长度一致的七天预报数组。")
    dates = [_parse_date(value) for value in daily["time"]]
    expected = [forecast_date + timedelta(days=i) for i in range(7)]
    if dates != expected:
        raise ValueError("天气响应日期与杭州当前七天预报窗口不一致。")
    result = {}
    for index, forecast_day in enumerate(dates):
        value = _day(daily["weather_code"][index], daily["temperature_2m_min"][index],
                     daily["temperature_2m_max"][index])
        if value is not None:
            result[forecast_day.isoformat()] = value
    if not result:
        raise ValueError("天气服务暂无有效预报。")
    return result


def _read_cache(store: WorkHoursStore, now: datetime) -> tuple[WeatherDays, str, bool] | None:
    try:
        cached = store.get_weather_cache(LOCATION_KEY)
        if cached is None:
            return None
        payload, stamp = cached
        if not isinstance(payload, dict) or not isinstance(stamp, str) or not stamp.endswith("Z"):
            return None
        fetched = datetime.fromisoformat(stamp[:-1] + "+00:00")
        forecast_date = _parse_date(payload["forecast_date"])
        # Future or internally inconsistent caches must not suppress a fetch.
        if fetched > now or forecast_date != fetched.astimezone(HANGZHOU_TZ).date():
            return None
        days = payload["days"]
        if not isinstance(days, dict) or not days:
            return None
        last = forecast_date + timedelta(days=6)
        validated = {}
        for key, item in days.items():
            work_date = _parse_date(key)
            if not forecast_date <= work_date <= last or not isinstance(item, dict):
                return None
            normalized = _day(item["code"], item["temperature_min"], item["temperature_max"])
            if normalized is None or item != normalized:
                return None
            validated[key] = normalized
        fresh = forecast_date == now.date() and now - fetched < timedelta(hours=1)
        return validated, stamp, fresh
    except (ValueError, TypeError, KeyError, OverflowError):
        # Cache contents are rebuildable and cannot prevent a new forecast.
        return None


def _fetch_json(url: str) -> object:
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def get_weather(
    store: WorkHoursStore,
    month: date,
    now: datetime | None = None,
    allow_network: bool = True,
    fetcher: Callable[[str], object] | None = None,
) -> WeatherResult:
    local_now = now if now is not None else datetime.now(timezone.utc)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=HANGZHOU_TZ)
    local_now = local_now.astimezone(HANGZHOU_TZ)
    today = local_now.date()
    end = today + timedelta(days=6)
    month_key = month.replace(day=1).isoformat()[:7]
    start_key, end_key = today.isoformat(), end.isoformat()

    def filtered(days: WeatherDays) -> WeatherDays:
        return {key: value for key, value in sorted(days.items())
                if start_key <= key <= end_key and key[:7] == month_key}

    def result(source, days=None, stamp=None, stale=False, warning=None):
        return WeatherResult(CITY, TIMEZONE, month_key, start_key, end_key,
                             source, stale, stamp, warning, days or {})

    if not start_key[:7] <= month_key <= end_key[:7]:
        return result("unavailable", warning="所选月份暂无预报，仅提供杭州今天起七天的天气。")

    cached = _read_cache(store, local_now)
    if cached is not None and cached[2]:
        visible = filtered(cached[0])
        if visible:
            return result("cache", visible, cached[1])
        return result("unavailable", warning="所选日期暂无有效天气预报。")

    if allow_network:
        # Storage reads have finished and closed before any network operation.
        try:
            days = _normalize((fetcher or _fetch_json)(FORECAST_URL), today)
        except (OSError, ValueError, HTTPException):
            pass
        else:
            stamp = local_now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            store.set_weather_cache(LOCATION_KEY, {"forecast_date": start_key, "days": days}, stamp)
            visible = filtered(days)
            if visible:
                return result("remote", visible, stamp)
            return result("unavailable", warning="所选日期暂无有效天气预报。")

    if cached is not None:
        visible = filtered(cached[0])
        if visible:
            return result("cache", visible, cached[1], stale=True,
                          warning="天气更新失败，暂时显示仍在预报范围内的缓存。")
    return result("unavailable", warning="天气暂不可用，请稍后重试。")
