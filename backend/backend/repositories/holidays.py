import json
import sqlite3
from collections.abc import Mapping
from typing import Any


def get_holiday_cache(
    conn: sqlite3.Connection,
    year: int,
) -> tuple[dict[str, object], str] | None:
    row = conn.execute(
        "SELECT payload_json, fetched_at FROM holiday_cache WHERE year = ?",
        (year,),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["payload_json"]), str(row["fetched_at"])


def set_holiday_cache(
    conn: sqlite3.Connection,
    year: int,
    payload: Mapping[str, object],
    fetched_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO holiday_cache (year, payload_json, fetched_at)
        VALUES (?, ?, ?)
        ON CONFLICT(year) DO UPDATE SET
            payload_json = excluded.payload_json,
            fetched_at = excluded.fetched_at
        """,
        (
            year,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            fetched_at,
        ),
    )


def list_holiday_cache(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT year, payload_json, fetched_at FROM holiday_cache ORDER BY year"
    )
    return {
        str(row["year"]): {
            "holidays": json.loads(row["payload_json"]),
            "fetchedAt": str(row["fetched_at"]),
        }
        for row in rows
    }


def replace_holiday_cache(
    conn: sqlite3.Connection,
    cache: Mapping[str, Mapping[str, Any]],
) -> None:
    conn.execute("DELETE FROM holiday_cache")
    for year, value in cache.items():
        set_holiday_cache(
            conn,
            int(year),
            value["holidays"],
            str(value["fetchedAt"]),
        )
