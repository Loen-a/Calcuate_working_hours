import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError

from backend.dependencies import get_db
from backend.services.backup import build_backup, restore_backup

router = APIRouter()


@router.get("/backup")
def download_backup(
    conn: sqlite3.Connection = Depends(get_db),
) -> Response:
    payload = build_backup(conn)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="workhours-{stamp}.json"'
            )
        },
    )


@router.post("/backup")
def upload_backup(
    file: UploadFile,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, int]:
    try:
        raw = json.loads(file.file.read().decode("utf-8"))
        return restore_backup(conn, raw)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        ValidationError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
