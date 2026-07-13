import sqlite3
import re
from datetime import date, datetime, timezone
from typing import Any

from backend.repositories.entries import list_entries, replace_entries
from backend.repositories.holidays import list_holiday_cache, replace_holiday_cache
from backend.repositories.preferences import get_theme, set_theme
from backend.schemas import PreferencesPayload, WorkEntryPayload, validate_work_date

UTC_TIMESTAMP_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z"
)


def _validate_utc_timestamp(raw: object, field_name: str) -> str:
    if not isinstance(raw, str) or UTC_TIMESTAMP_PATTERN.fullmatch(raw) is None:
        raise ValueError(f"{field_name} must be a canonical UTC timestamp")
    try:
        datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a canonical UTC timestamp"
        ) from exc
    return raw


def _validate_entries(raw: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ValueError("entries must be an object")
    validated: dict[str, dict[str, Any]] = {}
    for work_date, value in raw.items():
        if not isinstance(work_date, str):
            raise ValueError("entry date must be a string")
        validate_work_date(work_date)
        if (
            isinstance(value, dict)
            and "counts" in value
            and value["counts"] is not None
            and type(value["counts"]) is not bool
        ):
            raise ValueError("counts must be a boolean or null")
        payload = WorkEntryPayload.model_validate(value)
        validated[work_date] = payload.model_dump(
            by_alias=True,
            exclude_none=True,
        )
    return validated


def _validate_holiday_cache(raw: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ValueError("holidayCache must be an object")
    validated: dict[str, dict[str, Any]] = {}
    for year, value in raw.items():
        if (
            not isinstance(year, str)
            or re.fullmatch(r"[0-9]{4}", year) is None
            or int(year) < 2000
            or int(year) > 2100
        ):
            raise ValueError(
                "holiday cache year must be four digits in 2000..2100"
            )
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("holidays"), dict)
            or not isinstance(value.get("fetchedAt"), str)
        ):
            raise ValueError("holidayCache entry has invalid fields")
        fetched_at = _validate_utc_timestamp(
            value["fetchedAt"],
            "holiday fetchedAt",
        )
        holidays: dict[str, dict[str, str | bool]] = {}
        for month_day, info in value["holidays"].items():
            if not isinstance(month_day, str) or not isinstance(info, dict):
                raise ValueError("holiday entry has invalid fields")
            if re.fullmatch(r"[0-9]{2}-[0-9]{2}", month_day) is None:
                raise ValueError("holiday date must use MM-DD")
            try:
                date.fromisoformat(f"{year}-{month_day}")
            except ValueError as exc:
                raise ValueError("holiday date must use MM-DD") from exc
            if (
                not isinstance(info.get("name"), str)
                or type(info.get("isOffDay")) is not bool
            ):
                raise ValueError("holiday entry has invalid fields")
            holidays[month_day] = {
                "name": info["name"],
                "isOffDay": info["isOffDay"],
            }
        validated[year] = {
            "holidays": holidays,
            "fetchedAt": fetched_at,
        }
    return validated


def build_backup(conn: sqlite3.Connection) -> dict[str, object]:
    exported_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    return {
        "version": 2,
        "exportedAt": exported_at,
        "entries": list_entries(conn),
        "preferences": {"theme": get_theme(conn)},
        "holidayCache": list_holiday_cache(conn),
    }


def restore_backup(
    conn: sqlite3.Connection,
    raw: object,
) -> dict[str, int]:
    if not isinstance(raw, dict):
        raise ValueError("backup must be an object")
    version = raw.get("version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("unsupported backup version")
    _validate_utc_timestamp(raw.get("exportedAt"), "exportedAt")

    entries = _validate_entries(raw.get("entries"))
    if version == 1:
        with conn:
            replace_entries(conn, entries)
        return {"version": 1, "entries": len(entries), "holidayYears": 0}

    preferences = PreferencesPayload.model_validate(raw.get("preferences"))
    holiday_cache = _validate_holiday_cache(raw.get("holidayCache"))
    with conn:
        replace_entries(conn, entries)
        set_theme(conn, preferences.theme)
        replace_holiday_cache(conn, holiday_cache)
    return {
        "version": 2,
        "entries": len(entries),
        "holidayYears": len(holiday_cache),
    }
