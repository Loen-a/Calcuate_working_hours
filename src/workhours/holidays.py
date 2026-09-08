from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from http.client import HTTPException
from typing import Literal
from urllib.request import urlopen

from workhours.storage import WorkHoursStore


HolidayMap = dict[str, dict[str, str | bool]]
UPSTREAM_URLS = (
    "https://cdn.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json",
    "https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json",
)


@dataclass(frozen=True)
class HolidayResult:
    year: int
    holidays: HolidayMap
    source: Literal["cache", "remote", "fallback"]
    warning: str | None = None


def _normalize(year: int, raw: object) -> HolidayMap:
    if not isinstance(raw, dict) or not isinstance(raw.get("days"), list):
        raise ValueError("Holiday payload has no days array.")
    result: HolidayMap = {}
    for item in raw["days"]:
        if not isinstance(item, dict):
            raise ValueError("Holiday day must be an object.")
        date_value = item.get("date")
        name = item.get("name")
        is_off = item.get("isOffDay")
        if (
            not isinstance(date_value, str)
            or not isinstance(name, str)
            or not isinstance(is_off, bool)
        ):
            raise ValueError("Holiday day has invalid fields.")
        parsed = date.fromisoformat(date_value)
        if parsed.isoformat() != date_value or parsed.year != year:
            raise ValueError("Holiday day has invalid date.")
        month_day = date_value[5:]
        if month_day in result:
            raise ValueError("Holiday payload has duplicate date.")
        result[month_day] = {"name": name, "isOffDay": is_off}
    if not result:
        raise ValueError("Holiday payload has no holiday days.")
    return result


def _fetch_json(url: str) -> object:
    # urllib's default opener honors the user's environment proxy settings.
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def get_holidays(
    store: WorkHoursStore,
    year: int,
    refresh: bool = False,
    allow_network: bool = True,
    fetcher: Callable[[str], object] | None = None,
) -> HolidayResult:
    if type(year) is not int or not 2000 <= year <= 2100:
        raise ValueError("Year must be 2000..2100.")
    cached = store.get_holiday_cache(year)
    if cached is not None and not refresh:
        return HolidayResult(year, cached[0], "cache")

    if allow_network:
        fetch = fetcher or _fetch_json
        for template in UPSTREAM_URLS:
            try:
                holidays = _normalize(year, fetch(template.format(year=year)))
            except (OSError, ValueError, HTTPException):
                continue
            fetched_at = (
                datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )
            store.set_holiday_cache(year, holidays, fetched_at)
            return HolidayResult(year, holidays, "remote")

    if cached is not None:
        return HolidayResult(
            year, cached[0], "cache", "节假日刷新失败，继续使用本地缓存。"
        )
    warning = (
        "节假日数据获取失败，已按周末推断。"
        if allow_network
        else "节假日数据尚未缓存，暂按周末推断。"
    )
    return HolidayResult(year, {}, "fallback", warning)
