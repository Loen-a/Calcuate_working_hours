import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_db
from backend.services.holidays import get_holidays

router = APIRouter()


@router.get("/holidays/{year}")
async def read_holidays(
    year: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, object]:
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=422, detail="year must be 2000..2100")
    result = await get_holidays(conn, year)
    return {
        "year": result.year,
        "holidays": result.holidays,
        "source": result.source,
    }
