"""杭州美标 AQI 日最高预报；独立缓存，不参与工时业务。"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from http.client import HTTPException
from urllib.parse import urlencode
from urllib.request import urlopen

from workhours.storage import WorkHoursStore
from workhours.weather import CITY, HANGZHOU_TZ, TIMEZONE

CACHE_KEY = "hangzhou-air-quality-us"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality?" + urlencode({
    "latitude": "30.29365", "longitude": "120.16142", "timezone": TIMEZONE,
    "hourly": "us_aqi", "forecast_days": 7,
})

# Open-Meteo 返回 US AQI；不可套用国内 AQI 的等级名称或计算标准。
_LEVELS = [(50, "good", "良好"), (100, "moderate", "中等"),
           (150, "sensitive", "对敏感人群不健康"), (200, "unhealthy", "不健康"),
           (300, "very-unhealthy", "非常不健康"), (math.inf, "hazardous", "危险")]


@dataclass(frozen=True)
class AirQualityResult:
    city: str
    timezone: str
    month: str
    forecast_start: str
    forecast_end: str
    standard: str
    source: str
    stale: bool
    fetched_at: str | None
    warning: str | None
    days: dict[str, dict]


def _valid_value(value: object) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _day(value: float) -> dict:
    # 展示整数 AQI，先四舍五入，再选择同一数值对应的美标等级。
    aqi = int(math.floor(value + 0.5))
    for ceiling, category, label in _LEVELS:
        if aqi <= ceiling:
            return {"aqi_max": aqi, "category": category, "label": label}
    raise ValueError("无效 AQI")


def _normalize(raw: object, today: date) -> dict[str, dict]:
    if not isinstance(raw, dict) or not isinstance(raw.get("hourly"), dict):
        raise ValueError("缺少空气质量小时预报")
    if raw.get("timezone", TIMEZONE) != TIMEZONE or raw.get("utc_offset_seconds", 28800) != 28800:
        raise ValueError("空气质量时区不匹配")
    units = raw.get("hourly_units", {})
    if not isinstance(units, dict) or units.get("us_aqi", "USAQI") != "USAQI":
        raise ValueError("空气质量指数不是美标 AQI")
    hourly = raw["hourly"]
    start = datetime.combine(today, time())
    expected = [(start + timedelta(hours=i)).isoformat(timespec="minutes") for i in range(168)]
    values = hourly.get("us_aqi")
    if hourly.get("time") != expected or not isinstance(values, list) or len(values) != 168:
        raise ValueError("空气质量日期或小时数组不完整")
    days = {}
    for i in range(7):
        hours = values[i * 24:(i + 1) * 24]
        # 最末几天常为部分小时或全空值，不将其最大值冒充完整日最高值。
        if all(_valid_value(value) for value in hours):
            days[(today + timedelta(days=i)).isoformat()] = _day(max(hours))
    if not days:
        raise ValueError("暂无完整日空气质量预报")
    return days


def _cache(store: WorkHoursStore, now: datetime):
    try:
        cached = store.get_weather_cache(CACHE_KEY)
        if cached is None:
            return None
        payload, stamp = cached
        if not isinstance(payload, dict) or not isinstance(stamp, str) or not stamp.endswith("Z"):
            return None
        fetched = datetime.fromisoformat(stamp[:-1] + "+00:00")
        forecast_date = date.fromisoformat(payload["forecast_date"])
        if forecast_date.isoformat() != payload["forecast_date"] or payload.get("standard") != "US":
            return None
        if fetched > now or fetched.astimezone(HANGZHOU_TZ).date() != forecast_date:
            return None
        days = payload["days"]
        if not isinstance(days, dict) or not days:
            return None
        for key, item in days.items():
            day = date.fromisoformat(key)
            if day.isoformat() != key or not forecast_date <= day <= forecast_date + timedelta(days=6):
                return None
            if not isinstance(item, dict) or type(item.get("aqi_max")) is not int or not _valid_value(item["aqi_max"]):
                return None
            if item != _day(item["aqi_max"]):
                return None
        return days, stamp, forecast_date == now.date() and now - fetched < timedelta(hours=1)
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


def _fetch(url: str):
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def get_air_quality(store: WorkHoursStore, month: date, now: datetime | None = None,
                    allow_network: bool = True, fetcher=None) -> AirQualityResult:
    local_now = now if now is not None else datetime.now(timezone.utc)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=HANGZHOU_TZ)
    local_now = local_now.astimezone(HANGZHOU_TZ)
    today = local_now.date()
    start, end = today.isoformat(), (today + timedelta(days=6)).isoformat()
    month_key = month.replace(day=1).isoformat()[:7]

    def filtered(days):
        return {key: value for key, value in sorted(days.items()) if start <= key <= end and key[:7] == month_key}

    def result(source, days=None, stamp=None, stale=False, warning=None):
        return AirQualityResult(CITY, TIMEZONE, month_key, start, end, "US", source,
                                stale, stamp, warning, days or {})

    if not start[:7] <= month_key <= end[:7]:
        return result("unavailable", warning="所选月份暂无空气质量预报。")
    cached = _cache(store, local_now)
    if cached is not None and cached[2]:
        return result("cache", filtered(cached[0]), cached[1])
    if allow_network:
        try:
            days = _normalize((fetcher or _fetch)(AIR_QUALITY_URL), today)
        except (OSError, ValueError, HTTPException):
            pass
        else:
            stamp = local_now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            store.set_weather_cache(CACHE_KEY, {"forecast_date": start, "standard": "US", "days": days}, stamp)
            return result("remote", filtered(days), stamp)
    if cached is not None:
        visible = filtered(cached[0])
        if visible:
            return result("cache", visible, cached[1], stale=True, warning="空气质量更新失败，显示仍在预报范围内的缓存。")
    return result("unavailable", warning="暂无完整日空气质量预报，请稍后重试。")
