import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "workhours.db"
SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS work_entries (
    work_date  TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time   TEXT NOT NULL,
    counts     INTEGER NULL CHECK (counts IN (0, 1) OR counts IS NULL),
    leave      INTEGER NULL CHECK (leave IN (0, 1) OR leave IS NULL)
);
CREATE TABLE IF NOT EXISTS preferences (
    id    INTEGER PRIMARY KEY CHECK (id = 1),
    theme TEXT NOT NULL CHECK (theme IN ('cool', 'teal'))
);
CREATE TABLE IF NOT EXISTS holiday_cache (
    year         INTEGER PRIMARY KEY,
    payload_json TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);
"""

EXPECTED_COLUMNS = {
    "work_entries": (
        ("work_date", "TEXT", 0, 1),
        ("start_time", "TEXT", 1, 0),
        ("end_time", "TEXT", 1, 0),
        ("counts", "INTEGER", 0, 0),
        ("leave", "INTEGER", 0, 0),
    ),
    "preferences": (
        ("id", "INTEGER", 0, 1),
        ("theme", "TEXT", 1, 0),
    ),
    "holiday_cache": (
        ("year", "INTEGER", 0, 1),
        ("payload_json", "TEXT", 1, 0),
        ("fetched_at", "TEXT", 1, 0),
    ),
}

REQUIRED_CONSTRAINTS = {
    "work_entries": ("check(countsin(0,1)orcountsisnull)",),
    "preferences": (
        "check(id=1)",
        "check(themein('cool','teal'))",
    ),
}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _validate_schema(conn: sqlite3.Connection) -> None:
    for table, expected in EXPECTED_COLUMNS.items():
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        actual = tuple(
            (row["name"], row["type"].upper(), row["notnull"], row["pk"])
            for row in rows
        )
        if actual != expected:
            raise RuntimeError(f"{table} schema is incompatible")

        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        normalized_sql = "".join(str(row["sql"]).lower().split())
        if any(
            constraint not in normalized_sql
            for constraint in REQUIRED_CONSTRAINTS.get(table, ())
        ):
            raise RuntimeError(f"{table} schema constraints are incompatible")


def initialize_database(db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema version {version} is newer than supported "
                f"version {SCHEMA_VERSION}"
            )
        conn.executescript(SCHEMA_SQL)
        try:
            conn.execute(
                "ALTER TABLE work_entries ADD COLUMN leave INTEGER NULL "
                "CHECK (leave IN (0, 1) OR leave IS NULL)"
            )
        except sqlite3.OperationalError:
            pass  # column already exists
        _validate_schema(conn)
        conn.execute(
            "INSERT OR IGNORE INTO preferences (id, theme) VALUES (1, 'cool')"
        )
        if version == 0:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()
