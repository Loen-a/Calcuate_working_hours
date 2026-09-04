import sqlite3
from collections.abc import Mapping
from typing import Any


def _row_to_entry(row: sqlite3.Row) -> dict[str, str | bool]:
    entry: dict[str, str | bool] = {
        "in": row["start_time"],
        "out": row["end_time"],
    }
    if row["counts"] is not None:
        entry["counts"] = bool(row["counts"])
    if row["leave"] is not None:
        entry["leave"] = bool(row["leave"])
    return entry


def list_entries(conn: sqlite3.Connection) -> dict[str, dict[str, str | bool]]:
    rows = conn.execute(
        """
        SELECT work_date, start_time, end_time, counts, leave
        FROM work_entries
        ORDER BY work_date
        """
    )
    return {row["work_date"]: _row_to_entry(row) for row in rows}


def upsert_entry(
    conn: sqlite3.Connection,
    work_date: str,
    start_time: str,
    end_time: str,
    counts: bool | None,
    leave: bool = False,
) -> dict[str, str | bool]:
    conn.execute(
        """
        INSERT INTO work_entries (work_date, start_time, end_time, counts, leave)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(work_date) DO UPDATE SET
            start_time = excluded.start_time,
            end_time = excluded.end_time,
            counts = excluded.counts,
            leave = excluded.leave
        """,
        (work_date, start_time, end_time, counts, leave),
    )
    row = conn.execute(
        """
        SELECT start_time, end_time, counts, leave
        FROM work_entries
        WHERE work_date = ?
        """,
        (work_date,),
    ).fetchone()
    assert row is not None
    return _row_to_entry(row)


def delete_entry(conn: sqlite3.Connection, work_date: str) -> bool:
    cursor = conn.execute(
        "DELETE FROM work_entries WHERE work_date = ?",
        (work_date,),
    )
    return cursor.rowcount > 0


def replace_entries(
    conn: sqlite3.Connection,
    entries: Mapping[str, Mapping[str, Any]],
) -> None:
    conn.execute("DELETE FROM work_entries")
    for work_date, entry in entries.items():
        upsert_entry(
            conn,
            work_date,
            str(entry["in"]),
            str(entry["out"]),
            entry.get("counts"),
            bool(entry.get("leave", False)),
        )
