import sqlite3

from fastapi import APIRouter, Depends

from backend.dependencies import get_db
from backend.repositories.preferences import get_theme, set_theme
from backend.schemas import PreferencesPayload

router = APIRouter()


@router.get("/preferences")
def read_preferences(
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, str]:
    return {"theme": get_theme(conn)}


@router.put("/preferences")
def update_preferences(
    payload: PreferencesPayload,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, str]:
    with conn:
        theme = set_theme(conn, payload.theme)
    return {"theme": theme}
