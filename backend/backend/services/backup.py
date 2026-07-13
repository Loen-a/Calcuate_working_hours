import sqlite3
from datetime import datetime, timezone
from typing import Any

from backend.repositories.entries import list_entries, replace_entries
from backend.repositories.holidays import list_holiday_cache, replace_holiday_cache
from backend.repositories.preferences import get_theme, set_theme
from backend.schemas import PreferencesPayload, WorkEntryPayload, validate_work_date


def _validate_entries(raw: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ValueError("entries must be an object")
    validated: dict[str, dict[str, Any]] = {}
    for work_date, value in raw.items():
        if not isinstance(work_date, str):
            raise ValueError("entry date must be a string")
        validate_work_date(work_date)
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
            or not year.isdigit()
            or not isinstance(value, dict)
            or not isinstance(value.get("holidays"), dict)
            or not isinstance(value.get("fetchedAt"), str)
        ):
            raise ValueError("holidayCache entry has invalid fields")
        year_number = int(year)
        if year_number < 2000 or year_number > 2100:
            raise ValueError("holiday cache year must be 2000..2100")
        fetched_at = value["fetchedAt"]
        try:
            datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "holiday fetchedAt must be an ISO timestamp"
            ) from exc
        holidays: dict[str, dict[str, str | bool]] = {}
        for month_day, info in value["holidays"].items():
            if not isinstance(month_day, str) or not isinstance(info, dict):
                raise ValueError("holiday entry has invalid fields")
            try:
                datetime.strptime(f"{year}-{month_day}", "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("holiday date must use MM-DD") from exc
            if (
                not isinstance(info.get("name"), str)
                or not isinstance(info.get("isOffDay"), bool)
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
    if version not in (1, 2):
        raise ValueError("unsupported backup version")
    exported_at = raw.get("exportedAt")
    if not isinstance(exported_at, str):
        raise ValueError("exportedAt must be an ISO timestamp")
    try:
        datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("exportedAt must be an ISO timestamp") from exc

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
