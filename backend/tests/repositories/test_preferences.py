from pathlib import Path

from backend.db import connect, initialize_database
from backend.repositories.preferences import get_theme, set_theme


def test_theme_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        assert get_theme(conn) == "cool"
        assert set_theme(conn, "teal") == "teal"
        assert get_theme(conn) == "teal"
    finally:
        conn.close()
