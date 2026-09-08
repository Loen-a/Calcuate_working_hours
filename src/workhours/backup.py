"""Versioned, validated SQLite snapshots shared by both user interfaces."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any

from workhours.storage import WorkHoursStore


class InvalidBackup(ValueError):
    """A backup cannot be restored without losing or changing its meaning."""


_UTC_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z"
)
_SQLITE_MAX_INTEGER = (1 << 63) - 1


def build_backup(store: WorkHoursStore) -> dict[str, Any]:
    """Read every category through one connection and one consistent snapshot."""
    with store._connect() as connection:
        # A connection context alone does not open a transaction for SELECTs.
        connection.execute("BEGIN")
        entries = {
            row["work_date"]: {
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "lunch_minutes": row["lunch_minutes"],
            }
            for row in connection.execute(
                "SELECT work_date, start_time, end_time, lunch_minutes "
                "FROM entries ORDER BY work_date"
            )
        }
        settings = dict(connection.execute("SELECT key, value FROM settings"))
        intervals = [
            {
                "id": row["id"],
                "name": row["name"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "enabled": bool(row["enabled"]),
            }
            for row in connection.execute(
                "SELECT id, name, start_time, end_time, enabled "
                "FROM non_working_intervals ORDER BY start_time, end_time, id"
            )
        ]
        overrides = dict(connection.execute(
            "SELECT work_date, kind FROM calendar_overrides ORDER BY work_date"
        ))
        leave_days = [row[0] for row in connection.execute(
            "SELECT work_date FROM leave_days ORDER BY work_date"
        )]
        holiday_cache = {
            str(row["year"]): {
                "holidays": json.loads(row["payload_json"]),
                "fetchedAt": row["fetched_at"],
            }
            for row in connection.execute(
                "SELECT year, payload_json, fetched_at FROM holiday_cache ORDER BY year"
            )
        }

    return {
        "version": 3,
        "exportedAt": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
        "entries": entries,
        "settings": {
            "period": settings.get("period", "week"),
            "theme": settings.get("theme", "cool"),
        },
        "nonWorkingIntervals": intervals,
        "calendarOverrides": overrides,
        "leaveDays": leave_days,
        "holidayCache": holiday_cache,
    }


def restore_backup(store: WorkHoursStore, raw: object) -> dict[str, int]:
    """Validate the entire document before atomically replacing its categories."""
    backup = _validate_backup(raw)
    version = backup["version"]
    with store._connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM entries")
        connection.executemany(
            "INSERT INTO entries (work_date, start_time, end_time, lunch_minutes) "
            "VALUES (?, ?, ?, ?)",
            [
                (day, entry["start_time"], entry["end_time"], entry["lunch_minutes"])
                for day, entry in backup["entries"].items()
            ],
        )
        connection.execute("DELETE FROM leave_days")
        connection.executemany(
            "INSERT INTO leave_days (work_date) VALUES (?)",
            [(day,) for day in backup["leaveDays"]],
        )

        if version == 3:
            connection.execute("DELETE FROM non_working_intervals")
            connection.executemany(
                "INSERT INTO non_working_intervals "
                "(id, name, start_time, end_time, enabled) VALUES (?, ?, ?, ?, ?)",
                [
                    (item["id"], item["name"], item["start_time"],
                     item["end_time"], int(item["enabled"]))
                    for item in backup["nonWorkingIntervals"]
                ],
            )
            connection.execute("DELETE FROM calendar_overrides")
            connection.executemany(
                "INSERT INTO calendar_overrides (work_date, kind) VALUES (?, ?)",
                list(backup["calendarOverrides"].items()),
            )
            # Keep this marker even for an intentionally empty interval list.
            # Preserve internal settings that are not part of the backup format.
            connection.execute(
                "INSERT INTO settings (key, value) VALUES "
                "('non_working_intervals_initialized', '1') "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
            )

        if version >= 2:
            connection.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                list(backup["settings"].items()),
            )
            connection.execute("DELETE FROM holiday_cache")
            connection.executemany(
                "INSERT INTO holiday_cache (year, payload_json, fetched_at) "
                "VALUES (?, ?, ?)",
                [
                    (int(year), json.dumps(value["holidays"], ensure_ascii=False),
                     value["fetchedAt"])
                    for year, value in backup["holidayCache"].items()
                ],
            )

    return {
        "version": version,
        "entries": len(backup["entries"]),
        "leaveDays": len(backup["leaveDays"]),
        "holidayYears": len(backup.get("holidayCache", {})),
    }


def _object(raw: object, location: str) -> dict:
    if not isinstance(raw, dict):
        raise InvalidBackup(f"{location} 必须是对象。")
    return raw


def _fields(raw: object, required: set[str], location: str,
            optional: set[str] | None = None) -> dict:
    value = _object(raw, location)
    if set(value) - required - (optional or set()):
        raise InvalidBackup(f"{location} 包含未知字段，无法安全恢复。")
    if required - set(value):
        raise InvalidBackup(f"{location} 缺少必要字段。")
    return value


def _timestamp(raw: object, location: str) -> str:
    if not isinstance(raw, str) or not _UTC_TIMESTAMP.fullmatch(raw):
        raise InvalidBackup(f"{location} 必须是以 Z 结尾的 UTC 时间戳。")
    try:
        datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError as exc:
        raise InvalidBackup(f"{location} 不是有效的 UTC 时间戳。") from exc
    return raw


def _date(raw: object, location: str) -> str:
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        raise InvalidBackup(f"{location} 必须使用 YYYY-MM-DD 日期格式。")
    try:
        date.fromisoformat(raw)
    except ValueError as exc:
        raise InvalidBackup(f"{location} 不是有效日期：{raw}。") from exc
    return raw


def _time(raw: object, location: str, *, nullable: bool = False) -> str | None:
    if raw is None and nullable:
        return None
    if not isinstance(raw, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", raw):
        raise InvalidBackup(f"{location} 必须使用有效的 HH:MM 时间格式。")
    return raw


def _integer(raw: object, location: str, minimum: int = 0) -> int:
    if type(raw) is not int or not minimum <= raw <= _SQLITE_MAX_INTEGER:
        raise InvalidBackup(f"{location} 必须是 {minimum} 至 {_SQLITE_MAX_INTEGER} 之间的整数。")
    return raw


def _validate_entries(raw: object, version: int) -> tuple[dict, list[str]]:
    entries = {}
    leave_days = []
    for day, value in _object(raw, "entries").items():
        _date(day, "打卡日期")
        location = f"entries.{day}"
        if version == 3:
            item = _fields(value, {"start_time", "end_time", "lunch_minutes"}, location)
            start = _time(item["start_time"], f"{location}.start_time", nullable=True)
            end = _time(item["end_time"], f"{location}.end_time", nullable=True)
            lunch = item["lunch_minutes"]
            if lunch is not None:
                _integer(lunch, f"{location}.lunch_minutes")
        else:
            item = _fields(value, {"in", "out"}, location, {"counts", "leave"})
            if item.get("counts") is not None:
                raise InvalidBackup(
                    f"{location}.counts 与主分支工时规则不兼容，已停止整份导入；"
                    "请先在原应用核对并清除单条记录是否计入工时的特殊设置。"
                )
            if type(item.get("leave", False)) is not bool:
                raise InvalidBackup(f"{location}.leave 必须是布尔值。")
            start = _time(item["in"], f"{location}.in")
            end = _time(item["out"], f"{location}.out")
            lunch = None
            if item.get("leave", False):
                leave_days.append(day)
                if start == end == "00:00":
                    continue
                if start == "00:00" or end == "00:00":
                    raise InvalidBackup(
                        f"{location} 请假记录仅一侧为 00:00，存在占位时间与真实打卡的歧义，"
                        "已停止整份导入；请先在原应用核对并补全打卡，"
                        "或将纯请假记录的两侧都设为 00:00。"
                    )
        # Main permits incomplete and overnight punches. Never apply legacy
        # end-after-start restrictions or its independent work-hour formulas.
        entries[day] = {"start_time": start, "end_time": end, "lunch_minutes": lunch}
    return entries, leave_days


def _validate_intervals(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        raise InvalidBackup("nonWorkingIntervals 必须是数组。")
    result = []
    seen = set()
    for index, value in enumerate(raw):
        location = f"nonWorkingIntervals[{index}]"
        item = _fields(value, {"id", "name", "start_time", "end_time", "enabled"}, location)
        interval_id = _integer(item["id"], f"{location}.id", minimum=1)
        if interval_id in seen:
            raise InvalidBackup("nonWorkingIntervals 包含重复的 id。")
        seen.add(interval_id)
        if not isinstance(item["name"], str) or not item["name"].strip():
            raise InvalidBackup(f"{location}.name 必须是非空名称。")
        start = _time(item["start_time"], f"{location}.start_time")
        end = _time(item["end_time"], f"{location}.end_time")
        if start >= end:
            raise InvalidBackup(f"{location} 的开始时间必须早于结束时间。")
        if type(item["enabled"]) is not bool:
            raise InvalidBackup(f"{location}.enabled 必须是布尔值。")
        result.append(dict(item))
    return result


def _validate_holiday_cache(raw: object) -> dict:
    result = {}
    for year, value in _object(raw, "holidayCache").items():
        if (not isinstance(year, str) or not re.fullmatch(r"[0-9]{4}", year)
                or not 2000 <= int(year) <= 2100):
            raise InvalidBackup("holidayCache 年份必须是 2000 至 2100 之间的四位数字。")
        item = _fields(value, {"holidays", "fetchedAt"}, f"holidayCache.{year}")
        fetched_at = _timestamp(item["fetchedAt"], f"holidayCache.{year}.fetchedAt")
        holidays = {}
        for month_day, info in _object(item["holidays"], f"holidayCache.{year}.holidays").items():
            if not isinstance(month_day, str) or not re.fullmatch(r"[0-9]{2}-[0-9]{2}", month_day):
                raise InvalidBackup("节假日日期必须使用 MM-DD 格式。")
            _date(f"{year}-{month_day}", "节假日日期")
            holiday = _fields(info, {"name", "isOffDay"}, f"holidayCache.{year}.{month_day}")
            if not isinstance(holiday["name"], str) or type(holiday["isOffDay"]) is not bool:
                raise InvalidBackup("节假日 name 必须是字符串，isOffDay 必须是布尔值。")
            holidays[month_day] = dict(holiday)
        if not holidays:
            raise InvalidBackup(
                f"holidayCache.{year}.holidays 年度节假日缓存不能为空；"
                "请先在原应用刷新该年度节假日，或从备份中移除该年度缓存。"
            )
        result[year] = {"holidays": holidays, "fetchedAt": fetched_at}
    return result


def _validate_backup(raw: object) -> dict:
    value = _object(raw, "备份")
    version = value.get("version")
    if type(version) is not int or version not in (1, 2, 3):
        raise InvalidBackup("不支持的备份 version；仅支持整数版本 1、2、3。")
    required = {"version", "exportedAt", "entries"}
    if version == 2:
        required |= {"preferences", "holidayCache"}
    elif version == 3:
        required |= {"settings", "nonWorkingIntervals", "calendarOverrides", "leaveDays", "holidayCache"}
    _fields(value, required, "备份")
    _timestamp(value["exportedAt"], "exportedAt")
    entries, leave_days = _validate_entries(value["entries"], version)
    result = {"version": version, "entries": entries, "leaveDays": leave_days}

    if version == 3:
        settings = _fields(value["settings"], {"period", "theme"}, "settings")
        if settings["period"] not in ("week", "month"):
            raise InvalidBackup("settings.period 必须是 week 或 month。")
        result["nonWorkingIntervals"] = _validate_intervals(value["nonWorkingIntervals"])
        overrides = _object(value["calendarOverrides"], "calendarOverrides")
        for day, kind in overrides.items():
            _date(day, "手动日历日期")
            if kind not in ("holiday", "workday"):
                raise InvalidBackup("手动日历类型必须是 holiday 或 workday。")
        result["calendarOverrides"] = dict(overrides)
        if not isinstance(value["leaveDays"], list):
            raise InvalidBackup("leaveDays 必须是日期数组。")
        leave_days = [_date(day, "请假日期") for day in value["leaveDays"]]
        if len(set(leave_days)) != len(leave_days):
            raise InvalidBackup("leaveDays 包含重复日期。")
        result["leaveDays"] = leave_days
    elif version == 2:
        settings = _fields(value["preferences"], {"theme"}, "preferences")

    if version >= 2:
        if settings["theme"] not in ("cool", "teal"):
            raise InvalidBackup("theme 必须是 cool 或 teal。")
        result["settings"] = dict(settings)
        result["holidayCache"] = _validate_holiday_cache(value["holidayCache"])
    return result
