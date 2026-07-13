import sqlite3
from queue import Queue
from pathlib import Path
from threading import Event, Thread

from backend.db import SCHEMA_VERSION, connect, initialize_database


def test_connection_can_be_used_and_closed_after_thread_handoff(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "workhours.db"
    initialize_database(db_path)
    connections: Queue[sqlite3.Connection] = Queue()
    release_creator = Event()
    closed_after_handoff = Event()

    def create_connection() -> None:
        conn = connect(db_path)
        connections.put(conn)
        release_creator.wait()
        if not closed_after_handoff.is_set():
            conn.close()

    creator = Thread(target=create_connection)
    creator.start()
    conn = connections.get(timeout=5)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        closed_after_handoff.set()
    finally:
        release_creator.set()
        creator.join(timeout=5)

    assert version == SCHEMA_VERSION


def test_initialize_database_creates_schema_and_default_theme(tmp_path: Path) -> None:
    db_path = tmp_path / "workhours.db"
    initialize_database(db_path)

    conn = connect(db_path)
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        theme = conn.execute(
            "SELECT theme FROM preferences WHERE id = 1"
        ).fetchone()["theme"]
    finally:
        conn.close()

    assert tables >= {"work_entries", "preferences", "holiday_cache"}
    assert version == SCHEMA_VERSION == 1
    assert theme == "cool"


def test_initialize_database_rejects_newer_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "workhours.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA user_version = 99")
    conn.close()

    try:
        initialize_database(db_path)
    except RuntimeError as exc:
        assert "schema version 99" in str(exc)
    else:
        raise AssertionError("newer schema should be rejected")
