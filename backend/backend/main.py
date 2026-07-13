import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.api import backup, entries, health, holidays, preferences
from backend.db import DEFAULT_DB_PATH, initialize_database

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
DEFAULT_FRONTEND_DIR = REPOSITORY_ROOT / "frontend" / "dist"


def create_app(
    db_path: Path = DEFAULT_DB_PATH,
    frontend_dir: Path | None = DEFAULT_FRONTEND_DIR,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        initialize_database(app.state.db_path)
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.db_path = Path(db_path)
    app.state.frontend_dir = frontend_dir
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(entries.router, prefix="/api")
    app.include_router(preferences.router, prefix="/api")
    app.include_router(holidays.router, prefix="/api")
    app.include_router(backup.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        if app.state.frontend_dir is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "frontend build not found; "
                    "run npm --prefix frontend run build"
                ),
            )
        index_path = Path(app.state.frontend_dir) / "index.html"
        if not index_path.is_file():
            raise HTTPException(
                status_code=503,
                detail=(
                    "frontend build not found; "
                    "run npm --prefix frontend run build"
                ),
            )
        return FileResponse(index_path)

    @app.exception_handler(sqlite3.Error)
    async def sqlite_error_handler(
        request: Request,
        exc: sqlite3.Error,
    ) -> JSONResponse:
        logger.error(
            "SQLite request failed",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "database operation failed"},
        )

    return app


app = create_app()
