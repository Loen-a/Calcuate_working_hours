import sqlite3
from collections.abc import Iterator

from fastapi import Request

from backend.db import connect


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()
