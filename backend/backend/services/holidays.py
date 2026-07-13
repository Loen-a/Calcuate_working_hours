import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx

from backend.repositories.holidays import get_holiday_cache, set_holiday_cache

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


def _normalize(year: int, raw: object) -> HolidayMap:
    if not isinstance(raw, dict) or not isinstance(raw.get("days"), list):
        raise ValueError("holiday payload has no days array")
    result: HolidayMap = {}
    for item in raw["days"]:
        if not isinstance(item, dict):
            raise ValueError("holiday day must be an object")
        date_value = item.get("date")
        name = item.get("name")
        is_off = item.get("isOffDay")
        if (
            not isinstance(date_value, str)
            or not date_value.startswith(f"{year}-")
            or not isinstance(name, str)
            or not isinstance(is_off, bool)
        ):
            raise ValueError("holiday day has invalid fields")
        result[date_value[5:]] = {"name": name, "isOffDay": is_off}
    if not result:
        raise ValueError("holiday payload has no holiday days")
    return result


async def get_holidays(
    conn: sqlite3.Connection,
    year: int,
    client: httpx.AsyncClient | None = None,
) -> HolidayResult:
    cached = get_holiday_cache(conn, year)
    if cached is not None:
        return HolidayResult(year, cached[0], "cache")

    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=5.0, trust_env=False)
    try:
        for template in UPSTREAM_URLS:
            try:
                response = await http_client.get(template.format(year=year))
                response.raise_for_status()
                holidays = _normalize(year, response.json())
            except (httpx.HTTPError, ValueError):
                continue
            fetched_at = (
                datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )
            with conn:
                set_holiday_cache(conn, year, holidays, fetched_at)
            return HolidayResult(year, holidays, "remote")
    finally:
        if owns_client:
            await http_client.aclose()
    return HolidayResult(year, {}, "fallback")
