import sqlite3

from fastapi import APIRouter, Depends

from backend.dependencies import get_db

router = APIRouter()


@router.get("/health")
def health(conn: sqlite3.Connection = Depends(get_db)) -> dict[str, str]:
    conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}
