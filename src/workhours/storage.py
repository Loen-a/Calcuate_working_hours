from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, time
from pathlib import Path

from workhours.domain import (
    DayOverride,
    ForecastSettings,
    NonWorkingInterval,
    PeriodMode,
    WorkEntry,
    default_non_working_intervals,
)


_INTERVALS_INITIALIZED_KEY = "non_working_intervals_initialized"


class WorkHoursStore:
    def __init__(self, database_path: str | os.PathLike[str]) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def get_settings(self) -> ForecastSettings:
        period = self._get_setting("period", PeriodMode.WEEK.value)
        return ForecastSettings(
            period=PeriodMode(period),
            non_working_intervals=tuple(self.list_non_working_intervals()),
        )

    def set_period(self, period: PeriodMode) -> None:
        self._set_setting("period", period.value)

    def save_entry(self, entry: WorkEntry) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO entries (work_date, start_time, end_time, lunch_minutes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(work_date) DO UPDATE SET
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    lunch_minutes = excluded.lunch_minutes
                """,
                (
                    entry.work_date.isoformat(),
                    _format_time(entry.start),
                    _format_time(entry.end),
                    entry.lunch_minutes,
                ),
            )

    def get_entry(self, work_date: date) -> WorkEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT work_date, start_time, end_time, lunch_minutes
                FROM entries
                WHERE work_date = ?
                """,
                (work_date.isoformat(),),
            ).fetchone()

        return _entry_from_row(row) if row else None

    def list_entries(self, start: date, end: date) -> dict[date, WorkEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT work_date, start_time, end_time, lunch_minutes
                FROM entries
                WHERE work_date BETWEEN ? AND ?
                ORDER BY work_date
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()

        entries = [_entry_from_row(row) for row in rows]
        return {entry.work_date: entry for entry in entries}

    def set_override(self, work_date: date, override: DayOverride) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO calendar_overrides (work_date, kind)
                VALUES (?, ?)
                ON CONFLICT(work_date) DO UPDATE SET kind = excluded.kind
                """,
                (work_date.isoformat(), override.value),
            )

    def delete_override(self, work_date: date) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM calendar_overrides WHERE work_date = ?",
                (work_date.isoformat(),),
            )

    def list_overrides(self, start: date, end: date) -> dict[date, DayOverride]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT work_date, kind
                FROM calendar_overrides
                WHERE work_date BETWEEN ? AND ?
                ORDER BY work_date
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()

        return {
            date.fromisoformat(row["work_date"]): DayOverride(row["kind"])
            for row in rows
        }

    def list_non_working_intervals(self) -> list[NonWorkingInterval]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, start_time, end_time, enabled
                FROM non_working_intervals
                ORDER BY start_time, end_time, id
                """
            ).fetchall()
        return [_interval_from_row(row) for row in rows]

    def save_non_working_interval(
        self,
        interval: NonWorkingInterval,
    ) -> NonWorkingInterval:
        _validate_interval(interval)
        name = interval.name.strip()

        with self._connect() as connection:
            if interval.interval_id is None:
                cursor = connection.execute(
                    """
                    INSERT INTO non_working_intervals (
                        name,
                        start_time,
                        end_time,
                        enabled
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name,
                        _format_time(interval.start),
                        _format_time(interval.end),
                        int(interval.enabled),
                    ),
                )
                interval_id = int(cursor.lastrowid)
            else:
                cursor = connection.execute(
                    """
                    UPDATE non_working_intervals
                    SET name = ?, start_time = ?, end_time = ?, enabled = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        _format_time(interval.start),
                        _format_time(interval.end),
                        int(interval.enabled),
                        interval.interval_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise ValueError("Non-working interval does not exist.")
                interval_id = interval.interval_id

        return NonWorkingInterval(
            interval_id=interval_id,
            name=name,
            start=interval.start,
            end=interval.end,
            enabled=interval.enabled,
        )

    def delete_non_working_interval(self, interval_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM non_working_intervals WHERE id = ?",
                (interval_id,),
            )
            if cursor.rowcount == 0:
                raise ValueError("Non-working interval does not exist.")

    def _get_setting(self, key: str, default: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            ).fetchone()

        return row["value"] if row else default

    def _set_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entries (
                    work_date TEXT PRIMARY KEY,
                    start_time TEXT,
                    end_time TEXT,
                    lunch_minutes INTEGER
                );

                CREATE TABLE IF NOT EXISTS calendar_overrides (
                    work_date TEXT PRIMARY KEY,
                    kind TEXT NOT NULL CHECK (kind IN ('holiday', 'workday'))
                );

                CREATE TABLE IF NOT EXISTS non_working_intervals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1
                        CHECK (enabled IN (0, 1))
                );
                """
            )
            initialized = connection.execute(
                "SELECT 1 FROM settings WHERE key = ?",
                (_INTERVALS_INITIALIZED_KEY,),
            ).fetchone()
            if initialized is None:
                for interval in default_non_working_intervals():
                    connection.execute(
                        """
                        INSERT INTO non_working_intervals (
                            name,
                            start_time,
                            end_time,
                            enabled
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            interval.name,
                            _format_time(interval.start),
                            _format_time(interval.end),
                            int(interval.enabled),
                        ),
                    )
                connection.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    (_INTERVALS_INITIALIZED_KEY, "1"),
                )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def default_database_path() -> Path:
    configured = os.environ.get("WORKHOURS_DB_PATH")
    if configured:
        return Path(configured)
    return Path.cwd() / "workhours.sqlite3"


def _entry_from_row(row: sqlite3.Row) -> WorkEntry:
    return WorkEntry(
        work_date=date.fromisoformat(row["work_date"]),
        start=_parse_time(row["start_time"]),
        end=_parse_time(row["end_time"]),
        lunch_minutes=row["lunch_minutes"],
    )


def _interval_from_row(row: sqlite3.Row) -> NonWorkingInterval:
    return NonWorkingInterval(
        interval_id=row["id"],
        name=row["name"],
        start=time.fromisoformat(row["start_time"]),
        end=time.fromisoformat(row["end_time"]),
        enabled=bool(row["enabled"]),
    )


def _validate_interval(interval: NonWorkingInterval) -> None:
    if not interval.name.strip():
        raise ValueError("Non-working interval name is required.")
    if any(
        value.second or value.microsecond or value.tzinfo is not None
        for value in (interval.start, interval.end)
    ):
        raise ValueError("Non-working intervals must use minute precision.")
    if interval.start >= interval.end:
        raise ValueError("Non-working interval start must be before end.")


def _parse_time(value: str | None) -> time | None:
    return time.fromisoformat(value) if value else None


def _format_time(value: time | None) -> str | None:
    if value is None:
        return None
    return value.replace(second=0, microsecond=0).isoformat(timespec="minutes")