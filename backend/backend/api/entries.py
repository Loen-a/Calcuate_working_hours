import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.dependencies import get_db
from backend.repositories.entries import delete_entry, list_entries, upsert_entry
from backend.schemas import WorkEntryPayload, validate_work_date

router = APIRouter()


@router.get("/entries")
def get_entries(
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, dict[str, str | bool]]:
    return list_entries(conn)


@router.put("/entries/{work_date}")
def put_entry(
    work_date: str,
    payload: WorkEntryPayload,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, object]:
    try:
        work_date = validate_work_date(work_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with conn:
        entry = upsert_entry(
            conn,
            work_date,
            payload.start_time,
            payload.end_time,
            payload.counts,
        )
    return {"date": work_date, "entry": entry}


@router.delete("/entries/{work_date}", status_code=204)
def remove_entry(
    work_date: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> Response:
    try:
        work_date = validate_work_date(work_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with conn:
        removed = delete_entry(conn, work_date)
    if not removed:
        raise HTTPException(status_code=404, detail="work entry not found")
    return Response(status_code=204)
