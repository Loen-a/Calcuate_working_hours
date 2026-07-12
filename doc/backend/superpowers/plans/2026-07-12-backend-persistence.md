# Local Backend Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace browser persistence with a local FastAPI service backed by SQLite while preserving the existing work-hour calculations and user workflow.

**Architecture:** FastAPI serves both `frontend/dist/index.html` and a small `/api` surface. Route handlers validate HTTP data, focused repositories own all SQL, and services coordinate holiday fetching and transactional backup restore; the React app consumes the API through one adapter and keeps derived calculations in the browser.

**Tech Stack:** Python 3.11+, Poetry 2.2.1, FastAPI, Uvicorn, Python `sqlite3`, HTTPX, pytest, React 19, TypeScript 7, Vite 8, Vitest.

## Global Constraints

- The application is single-user and listens on `127.0.0.1` only; do not add authentication, accounts, LAN access, or cloud deployment.
- SQLite at `backend/data/workhours.db` is the only persistent source for entries, theme, and holiday cache.
- Use an in-project Poetry environment at `backend/.venv`. Never run global `pip install`; run Python commands through `poetry -C backend run`.
- Keep one work entry per ISO date. Do not add split shifts or overnight entries.
- Store only raw `in`, `out`, and optional `counts` values. Keep net-hours, balance, chart, and recommendation calculations in the existing frontend.
- Keep component props named `y`/`m`; `viewY`/`viewM` remain private `App.tsx` state names.
- Keep `npm --prefix frontend run build` as `tsc --noEmit && vite build`.
- Export names must be unique to the second: `workhours-YYYY-MM-DD-HH-mm-ss.json`.
- Do not add ORM, Alembic, localStorage fallback, optimistic writes, or unrelated refactors.
- The current workspace has no `.git` directory. Do not run `git init` without explicit user authorization. Each task therefore ends with a verification checkpoint; if the user creates a repository before execution, use the suggested commit shown at that checkpoint.

## File Structure

### Python backend

- Create `backend/pyproject.toml` and `backend/poetry.lock` — Poetry dependency and lock metadata.
- Create `backend/poetry.toml` — project-local `.venv` setting.
- Create `backend/backend/__init__.py` — Python package marker.
- Create `backend/backend/db.py` — paths, SQLite connections, schema initialization, schema version.
- Create `backend/backend/schemas.py` — Pydantic request/response validation and JSON aliases.
- Create `backend/backend/main.py` — app factory, lifespan, CORS, exception mapping, API registration, frontend serving.
- Create `backend/backend/dependencies.py` — request-scoped SQLite connection dependency.
- Create `backend/backend/api/__init__.py` — API package marker.
- Create `backend/backend/api/health.py` — database health endpoint.
- Create `backend/backend/api/entries.py` — work-entry CRUD routes.
- Create `backend/backend/api/preferences.py` — theme routes.
- Create `backend/backend/api/holidays.py` — holiday route.
- Create `backend/backend/api/backup.py` — versioned backup download/upload routes.
- Create `backend/backend/repositories/__init__.py` — repository package marker.
- Create `backend/backend/repositories/entries.py` — entry SQL.
- Create `backend/backend/repositories/preferences.py` — preference SQL.
- Create `backend/backend/repositories/holidays.py` — holiday-cache SQL.
- Create `backend/backend/services/__init__.py` — service package marker.
- Create `backend/backend/services/holidays.py` — cache-first holiday retrieval.
- Create `backend/backend/services/backup.py` — export building, validation, and transactional restore.

### Tests and frontend

- Create `backend/tests/` repository, API, holiday-service, and backup tests using temporary SQLite databases.
- Create `frontend/src/lib/api.ts` and `frontend/src/lib/api.test.ts` — the only frontend HTTP adapter and its tests.
- Create `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, and `frontend/src/App.test.tsx` — browser-like frontend test setup.
- Modify `frontend/src/App.tsx`, `frontend/src/components/Header.tsx`, and `frontend/src/components/EntryModal.tsx` for asynchronous server-confirmed operations.
- Modify `frontend/src/lib/holidays.ts` and `frontend/src/lib/useTheme.ts` to remove browser persistence and direct CDN access.
- Delete `frontend/src/lib/storage.ts` and `frontend/src/lib/backup.ts`.
- Modify `README.md` and `doc/backend/业务规则/数据存储与备份.md`, and add a project log.

---

### Task 1: Separate Frontend, Backend, and Documentation Trees

**Files:**
- Move: `src/` → `frontend/src/`
- Move: `index.html`, `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, and `test-runtime.mjs` → `frontend/`
- Move when present: generated `node_modules/` and `dist/` → `frontend/`
- Move: `data/` → `backend/data/`
- Move: existing frontend rules/logs/pitfalls → `doc/frontend/`
- Keep/Create: backend storage rules, specs, plans, and logs under `doc/backend/`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `doc/CLAUDE.md`

**Interfaces:**
- Consumes: the current pure-frontend repository layout.
- Produces: stable `frontend/`, `backend/`, `doc/frontend/`, and `doc/backend/` boundaries used by every later task.

- [ ] **Step 1: Capture the baseline before moving anything**

Run from the repository root:

```powershell
npm run build
rg --files -g '!node_modules' -g '!dist'
```

Expected: the current frontend build PASSes and the file list matches the pre-backend layout. Save the build output as the before-move baseline.

- [ ] **Step 2: Verify every move target stays inside the repository**

Run:

```powershell
$root = (Resolve-Path '.').Path
$targets = @(
  (Join-Path $root 'frontend'),
  (Join-Path $root 'backend'),
  (Join-Path $root 'doc\frontend'),
  (Join-Path $root 'doc\backend')
)
$targets | ForEach-Object {
  if (-not $_.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Target escaped repository root: $_"
  }
  $_
}
```

Expected: four absolute paths under `D:\MyCode\VibeCoding\WorkTimeStatistics`.

- [ ] **Step 3: Create boundaries and move the existing frontend**

Run these moves in PowerShell after Step 2 passes:

```powershell
New-Item -ItemType Directory -Force -Path 'frontend', 'backend', 'doc\frontend', 'doc\backend', 'doc\backend\业务规则' | Out-Null
Move-Item -LiteralPath 'src' -Destination 'frontend\src'
@('index.html', 'package.json', 'package-lock.json', 'vite.config.ts', 'tsconfig.json', 'test-runtime.mjs') |
  ForEach-Object { Move-Item -LiteralPath $_ -Destination 'frontend' }
if (Test-Path -LiteralPath 'node_modules') {
  Move-Item -LiteralPath 'node_modules' -Destination 'frontend\node_modules'
}
if (Test-Path -LiteralPath 'dist') {
  Move-Item -LiteralPath 'dist' -Destination 'frontend\dist'
}
Move-Item -LiteralPath 'data' -Destination 'backend\data'
Move-Item -LiteralPath 'doc\业务规则' -Destination 'doc\frontend\业务规则'
Move-Item -LiteralPath 'doc\项目日志' -Destination 'doc\frontend\项目日志'
Move-Item -LiteralPath 'doc\踩坑记录' -Destination 'doc\frontend\踩坑记录'
Move-Item -LiteralPath 'doc\frontend\业务规则\数据存储与备份.md' -Destination 'doc\backend\业务规则\数据存储与备份.md'
```

Do not move root `AGENTS.md`, `CLAUDE.md`, or `README.md`; they are shared project entry points.

- [ ] **Step 4: Update shared path documentation immediately**

In `AGENTS.md`, change source references to `frontend/src/...`, frontend commands to `npm --prefix frontend ...`, and detailed-document references to `doc/frontend/` or `doc/backend/`.

Replace `doc/CLAUDE.md` with this directory contract:

```markdown
# doc/

详细文档按所属代码边界分开：

- `frontend/`：前端业务规则、项目日志和踩坑记录。
- `backend/`：后端存储规则、设计规格、实施计划、项目日志和踩坑记录。

前端文档不得写入 backend，后端文档不得写入 frontend。跨端总览只放根 `README.md`。
```

Update the project-structure block in `README.md` so it names `frontend/`, `backend/`, `doc/frontend/`, and `doc/backend/`; do not yet claim that backend code exists.

- [ ] **Step 5: Verify the move before creating backend code**

Run:

```powershell
npm --prefix frontend run build
rg --files -g '!node_modules' -g '!dist'
Get-ChildItem -Force
```

Expected:

- The same frontend build that passed in Step 1 still PASSes.
- No root `src/`, `index.html`, `package.json`, `vite.config.ts`, `node_modules/`, `dist/`, or `data/` remains.
- Frontend runtime files are under `frontend/`.
- Legacy JSON is under `backend/data/`.
- Existing frontend docs are under `doc/frontend/`; backend persistence docs are under `doc/backend/`.

Stop here and fix paths if the frontend build fails. Do not start Task 2 until this checkpoint passes.

- [ ] **Step 6: Record the checkpoint**

If Git exists:

```powershell
git add frontend backend/data doc AGENTS.md README.md
git commit -m "chore: separate frontend and backend trees"
```

Otherwise record the before/after file lists and passing build output without initializing Git.

### Task 2: Poetry Environment and SQLite Schema

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/poetry.lock`
- Create: `backend/poetry.toml`
- Create: `.gitignore`
- Create: `backend/backend/__init__.py`
- Create: `backend/backend/db.py`
- Create: `backend/tests/test_db.py`

**Interfaces:**
- Produces: `DEFAULT_DB_PATH: Path`, `SCHEMA_VERSION: int`, `connect(db_path: Path) -> sqlite3.Connection`, and `initialize_database(db_path: Path = DEFAULT_DB_PATH) -> None`.
- Consumes: nothing from later tasks.

- [ ] **Step 1: Create the isolated Poetry project**

Run:

```powershell
poetry -C backend init --no-interaction --name work-time-statistics-backend --python ">=3.11,<4.0"
poetry -C backend config virtualenvs.in-project true --local
poetry -C backend add fastapi "uvicorn[standard]" httpx python-multipart
poetry -C backend add --group dev pytest pytest-cov
```

Expected:

- `backend/poetry.toml` contains `virtualenvs.in-project = true`.
- `backend/pyproject.toml` and `backend/poetry.lock` exist.
- `poetry -C backend env info --path` ends in `WorkTimeStatistics/backend/.venv`.

Add these exact ignore rules without removing existing user rules:

```gitignore
/backend/.venv/
/backend/data/*.db
/backend/data/*.db-*
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
```

- [ ] **Step 2: Write the failing schema test**

Create `backend/tests/test_db.py`:

```python
import sqlite3
from pathlib import Path

from backend.db import SCHEMA_VERSION, connect, initialize_database


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
```

- [ ] **Step 3: Run the test and verify failure**

Run: `poetry -C backend run pytest tests/test_db.py -v`

Expected: FAIL during collection because `backend.db` does not exist.

- [ ] **Step 4: Implement the database module**

Create an empty `backend/backend/__init__.py` and create `backend/backend/db.py`:

```python
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
    counts     INTEGER NULL CHECK (counts IN (0, 1) OR counts IS NULL)
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


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


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
        if version == 0:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT OR IGNORE INTO preferences (id, theme) VALUES (1, 'cool')"
            )
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Verify schema and Poetry isolation**

Run:

```powershell
poetry -C backend run pytest tests/test_db.py -v
poetry -C backend env info --path
```

Expected: 2 tests PASS and the environment path ends in `WorkTimeStatistics/backend/.venv`.

- [ ] **Step 6: Record the checkpoint**

If Git exists by execution time:

```powershell
git add backend/pyproject.toml backend/poetry.lock backend/poetry.toml .gitignore backend/backend backend/tests/test_db.py
git commit -m "feat: initialize local sqlite backend"
```

Otherwise record the passing commands and changed files without initializing Git.

### Task 3: Focused SQLite Repositories

**Files:**
- Create: `backend/backend/repositories/__init__.py`
- Create: `backend/backend/repositories/entries.py`
- Create: `backend/backend/repositories/preferences.py`
- Create: `backend/backend/repositories/holidays.py`
- Create: `backend/tests/repositories/test_entries.py`
- Create: `backend/tests/repositories/test_preferences.py`
- Create: `backend/tests/repositories/test_holidays.py`

**Interfaces:**
- Consumes: `connect` and the initialized Task 2 schema.
- Produces:
  - `list_entries(conn) -> dict[str, dict[str, str | bool]]`
  - `upsert_entry(conn, work_date, start_time, end_time, counts) -> dict[str, str | bool]`
  - `delete_entry(conn, work_date) -> bool`
  - `replace_entries(conn, entries) -> None`
  - `get_theme(conn) -> str` and `set_theme(conn, theme) -> str`
  - `get_holiday_cache(conn, year) -> tuple[dict[str, object], str] | None`
  - `set_holiday_cache(conn, year, payload, fetched_at) -> None`
  - `list_holiday_cache(conn) -> dict[str, dict[str, object]]`
  - `replace_holiday_cache(conn, cache) -> None`

- [ ] **Step 1: Write failing repository tests**

Create `backend/tests/repositories/test_entries.py`:

```python
from pathlib import Path

from backend.db import connect, initialize_database
from backend.repositories.entries import (
    delete_entry,
    list_entries,
    replace_entries,
    upsert_entry,
)


def test_entry_upsert_delete_and_replace(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        upsert_entry(conn, "2026-07-12", "08:00", "18:30", True)
        upsert_entry(conn, "2026-07-12", "08:10", "18:40", None)
        assert list_entries(conn) == {
            "2026-07-12": {"in": "08:10", "out": "18:40"}
        }

        replace_entries(
            conn,
            {
                "2026-07-13": {
                    "in": "08:00",
                    "out": "18:00",
                    "counts": False,
                }
            },
        )
        assert list_entries(conn) == {
            "2026-07-13": {
                "in": "08:00",
                "out": "18:00",
                "counts": False,
            }
        }
        assert delete_entry(conn, "2026-07-13") is True
        assert delete_entry(conn, "2026-07-13") is False
    finally:
        conn.close()
```

Create `backend/tests/repositories/test_preferences.py`:

```python
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
```

Create `backend/tests/repositories/test_holidays.py`:

```python
from pathlib import Path

from backend.db import connect, initialize_database
from backend.repositories.holidays import (
    get_holiday_cache,
    list_holiday_cache,
    replace_holiday_cache,
    set_holiday_cache,
)


def test_holiday_cache_round_trip_and_replace(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        payload = {"01-01": {"name": "元旦", "isOffDay": True}}
        set_holiday_cache(conn, 2026, payload, "2026-01-01T00:00:00Z")
        assert get_holiday_cache(conn, 2026) == (
            payload,
            "2026-01-01T00:00:00Z",
        )

        replace_holiday_cache(
            conn,
            {
                "2027": {
                    "holidays": {},
                    "fetchedAt": "2027-01-01T00:00:00Z",
                }
            },
        )
        assert get_holiday_cache(conn, 2026) is None
        assert list_holiday_cache(conn) == {
            "2027": {
                "holidays": {},
                "fetchedAt": "2027-01-01T00:00:00Z",
            }
        }
    finally:
        conn.close()
```

- [ ] **Step 2: Run tests and verify failure**

Run: `poetry -C backend run pytest tests/repositories -v`

Expected: FAIL because `backend.repositories` does not exist.

- [ ] **Step 3: Implement the entry repository**

Create an empty `backend/backend/repositories/__init__.py` and create `backend/backend/repositories/entries.py`:

```python
import sqlite3
from collections.abc import Mapping
from typing import Any


def _row_to_entry(row: sqlite3.Row) -> dict[str, str | bool]:
    entry: dict[str, str | bool] = {
        "in": row["start_time"],
        "out": row["end_time"],
    }
    if row["counts"] is not None:
        entry["counts"] = bool(row["counts"])
    return entry


def list_entries(conn: sqlite3.Connection) -> dict[str, dict[str, str | bool]]:
    rows = conn.execute(
        """
        SELECT work_date, start_time, end_time, counts
        FROM work_entries
        ORDER BY work_date
        """
    )
    return {row["work_date"]: _row_to_entry(row) for row in rows}


def upsert_entry(
    conn: sqlite3.Connection,
    work_date: str,
    start_time: str,
    end_time: str,
    counts: bool | None,
) -> dict[str, str | bool]:
    conn.execute(
        """
        INSERT INTO work_entries (work_date, start_time, end_time, counts)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(work_date) DO UPDATE SET
            start_time = excluded.start_time,
            end_time = excluded.end_time,
            counts = excluded.counts
        """,
        (work_date, start_time, end_time, counts),
    )
    row = conn.execute(
        """
        SELECT start_time, end_time, counts
        FROM work_entries
        WHERE work_date = ?
        """,
        (work_date,),
    ).fetchone()
    assert row is not None
    return _row_to_entry(row)


def delete_entry(conn: sqlite3.Connection, work_date: str) -> bool:
    cursor = conn.execute(
        "DELETE FROM work_entries WHERE work_date = ?",
        (work_date,),
    )
    return cursor.rowcount > 0


def replace_entries(
    conn: sqlite3.Connection,
    entries: Mapping[str, Mapping[str, Any]],
) -> None:
    conn.execute("DELETE FROM work_entries")
    for work_date, entry in entries.items():
        upsert_entry(
            conn,
            work_date,
            str(entry["in"]),
            str(entry["out"]),
            entry.get("counts"),
        )
```

- [ ] **Step 4: Implement preference and holiday repositories**

Create `backend/backend/repositories/preferences.py`:

```python
import sqlite3


def get_theme(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT theme FROM preferences WHERE id = 1"
    ).fetchone()
    if row is None:
        raise RuntimeError("preferences row is missing")
    return str(row["theme"])


def set_theme(conn: sqlite3.Connection, theme: str) -> str:
    conn.execute(
        "UPDATE preferences SET theme = ? WHERE id = 1",
        (theme,),
    )
    return theme
```

Create `backend/backend/repositories/holidays.py`:

```python
import json
import sqlite3
from collections.abc import Mapping
from typing import Any


def get_holiday_cache(
    conn: sqlite3.Connection,
    year: int,
) -> tuple[dict[str, object], str] | None:
    row = conn.execute(
        "SELECT payload_json, fetched_at FROM holiday_cache WHERE year = ?",
        (year,),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["payload_json"]), str(row["fetched_at"])


def set_holiday_cache(
    conn: sqlite3.Connection,
    year: int,
    payload: Mapping[str, object],
    fetched_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO holiday_cache (year, payload_json, fetched_at)
        VALUES (?, ?, ?)
        ON CONFLICT(year) DO UPDATE SET
            payload_json = excluded.payload_json,
            fetched_at = excluded.fetched_at
        """,
        (
            year,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            fetched_at,
        ),
    )


def list_holiday_cache(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT year, payload_json, fetched_at FROM holiday_cache ORDER BY year"
    )
    return {
        str(row["year"]): {
            "holidays": json.loads(row["payload_json"]),
            "fetchedAt": str(row["fetched_at"]),
        }
        for row in rows
    }


def replace_holiday_cache(
    conn: sqlite3.Connection,
    cache: Mapping[str, Mapping[str, Any]],
) -> None:
    conn.execute("DELETE FROM holiday_cache")
    for year, value in cache.items():
        set_holiday_cache(
            conn,
            int(year),
            value["holidays"],
            str(value["fetchedAt"]),
        )
```

- [ ] **Step 5: Run repository tests**

Run: `poetry -C backend run pytest tests/repositories -v`

Expected: 3 tests PASS.

- [ ] **Step 6: Record the checkpoint**

If Git exists:

```powershell
git add backend/backend/repositories backend/tests/repositories
git commit -m "feat: add sqlite repositories"
```

Otherwise record the passing repository test command and changed files.

### Task 4: Validation Models and Core API

**Files:**
- Create: `backend/backend/schemas.py`
- Create: `backend/backend/dependencies.py`
- Create: `backend/backend/main.py`
- Create: `backend/backend/api/__init__.py`
- Create: `backend/backend/api/health.py`
- Create: `backend/backend/api/entries.py`
- Create: `backend/backend/api/preferences.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/api/test_core_api.py`

**Interfaces:**
- Consumes: Task 2 connection/init functions and Task 3 entry/preference repositories.
- Produces: `create_app(db_path: Path, frontend_dir: Path | None = None) -> FastAPI`, `app`, `get_db`, `WorkEntryPayload`, `PreferencesPayload`, `GET /api/health`, `GET /api/entries`, `PUT /api/entries/{date}`, `DELETE /api/entries/{date}`, `GET /api/preferences`, and `PUT /api/preferences`.

- [ ] **Step 1: Write failing core API tests**

Create `backend/tests/conftest.py`:

```python
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(tmp_path / "test.db", frontend_dir=None)
    with TestClient(app) as test_client:
        yield test_client
```

Create `backend/tests/api/test_core_api.py`:

```python
from fastapi.testclient import TestClient


def test_health_entries_and_preferences(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/entries").json() == {}
    assert client.get("/api/preferences").json() == {"theme": "cool"}

    saved = client.put(
        "/api/entries/2026-07-12",
        json={"in": "08:00", "out": "18:30", "counts": True},
    )
    assert saved.status_code == 200
    assert saved.json() == {
        "date": "2026-07-12",
        "entry": {"in": "08:00", "out": "18:30", "counts": True},
    }
    assert client.put("/api/preferences", json={"theme": "teal"}).json() == {
        "theme": "teal"
    }
    assert client.delete("/api/entries/2026-07-12").status_code == 204
    assert client.delete("/api/entries/2026-07-12").status_code == 404


def test_invalid_entry_is_rejected(client: TestClient) -> None:
    response = client.put(
        "/api/entries/not-a-date",
        json={"in": "18:00", "out": "08:00"},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests and verify failure**

Run: `poetry -C backend run pytest tests/api/test_core_api.py -v`

Expected: FAIL because `backend.main` and API modules do not exist.

- [ ] **Step 3: Implement validated request models and the DB dependency**

Create `backend/backend/schemas.py`:

```python
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkEntryPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    start_time: str = Field(alias="in", serialization_alias="in")
    end_time: str = Field(alias="out", serialization_alias="out")
    counts: bool | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:MM") from exc
        return parsed.strftime("%H:%M")

    @model_validator(mode="after")
    def validate_order(self) -> "WorkEntryPayload":
        start = datetime.strptime(self.start_time, "%H:%M")
        end = datetime.strptime(self.end_time, "%H:%M")
        if end <= start:
            raise ValueError("end time must be later than start time")
        return self


class PreferencesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: Literal["cool", "teal"]


def validate_work_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return value
```

Create `backend/backend/dependencies.py`:

```python
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
```

- [ ] **Step 4: Implement health, entry, and preference routes**

Create empty `backend/backend/api/__init__.py` and these route files:

```python
# backend/backend/api/health.py
import sqlite3

from fastapi import APIRouter, Depends

from backend.dependencies import get_db

router = APIRouter()


@router.get("/health")
def health(conn: sqlite3.Connection = Depends(get_db)) -> dict[str, str]:
    conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}
```

```python
# backend/backend/api/entries.py
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
```

```python
# backend/backend/api/preferences.py
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
```

- [ ] **Step 5: Implement the app factory and SQLite error mapping**

Create `backend/backend/main.py`:

```python
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import entries, health, preferences
from backend.db import DEFAULT_DB_PATH, initialize_database

logger = logging.getLogger(__name__)


def create_app(
    db_path: Path = DEFAULT_DB_PATH,
    frontend_dir: Path | None = None,
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
```

- [ ] **Step 6: Run core API and earlier tests**

Run:

```powershell
poetry -C backend run pytest tests/test_db.py tests/repositories tests/api/test_core_api.py -v
```

Expected: all schema, repository, and core API tests PASS.

- [ ] **Step 7: Record the checkpoint**

If Git exists:

```powershell
git add backend/backend backend/tests/conftest.py backend/tests/api/test_core_api.py
git commit -m "feat: expose entry and preference api"
```

Otherwise record the passing core API command and changed files.
### Task 5: Cache-First Holiday Service

**Files:**
- Create: `backend/backend/services/__init__.py`
- Create: `backend/backend/services/holidays.py`
- Create: `backend/backend/api/holidays.py`
- Modify: `backend/backend/main.py`
- Create: `backend/tests/services/test_holidays.py`
- Create: `backend/tests/api/test_holidays_api.py`

**Interfaces:**
- Consumes: Task 3 holiday repository and Task 4 `get_db`/app factory.
- Produces: `HolidayResult`, `get_holidays(conn, year, client=None) -> HolidayResult`, and `GET /api/holidays/{year}`.

- [ ] **Step 1: Write failing service tests with simulated HTTP**

Create `backend/tests/services/test_holidays.py`:

```python
from pathlib import Path

import httpx
import pytest

from backend.db import connect, initialize_database
from backend.repositories.holidays import set_holiday_cache
from backend.services.holidays import get_holidays


@pytest.mark.anyio
async def test_cache_hit_does_not_call_remote(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    payload = {"01-01": {"name": "元旦", "isOffDay": True}}
    with conn:
        set_holiday_cache(conn, 2026, payload, "2026-01-01T00:00:00Z")

    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError("remote request should not happen")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(unexpected_request)
    ) as client:
        result = await get_holidays(conn, 2026, client)
    conn.close()

    assert result.source == "cache"
    assert result.holidays == payload


@pytest.mark.anyio
async def test_remote_success_is_cached(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)

    def remote(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "days": [
                    {
                        "name": "元旦",
                        "date": "2026-01-01",
                        "isOffDay": True,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(remote)
    ) as client:
        first = await get_holidays(conn, 2026, client)
        second = await get_holidays(conn, 2026, client)
    conn.close()

    assert first.source == "remote"
    assert second.source == "cache"
    assert first.holidays["01-01"]["name"] == "元旦"


@pytest.mark.anyio
async def test_both_remote_sources_fail_without_caching(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    calls = 0

    def failed(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(failed)
    ) as client:
        result = await get_holidays(conn, 2026, client)
    count = conn.execute(
        "SELECT COUNT(*) FROM holiday_cache WHERE year = 2026"
    ).fetchone()[0]
    conn.close()

    assert calls == 2
    assert result.source == "fallback"
    assert result.holidays == {}
    assert count == 0
```

Add this fixture to `backend/tests/conftest.py`:

```python
@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
```

- [ ] **Step 2: Run the service tests and verify failure**

Run: `poetry -C backend run pytest tests/services/test_holidays.py -v`

Expected: FAIL because `backend.services.holidays` does not exist.

- [ ] **Step 3: Implement cache-first retrieval**

Create empty `backend/backend/services/__init__.py` and `backend/backend/services/holidays.py`:

```python
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx

from backend.repositories.holidays import get_holiday_cache, set_holiday_cache

HolidayMap = dict[str, dict[str, str | bool]]
UPSTREAM_URLS = (
    "https://cdn.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json",
    "https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json",
)


@dataclass(frozen=True)
class HolidayResult:
    year: int
    holidays: HolidayMap
    source: Literal["cache", "remote", "fallback"]


def _normalize(year: int, raw: object) -> HolidayMap:
    if not isinstance(raw, dict) or not isinstance(raw.get("days"), list):
        raise ValueError("holiday payload has no days array")
    result: HolidayMap = {}
    for item in raw["days"]:
        if not isinstance(item, dict):
            raise ValueError("holiday day must be an object")
        date_value = item.get("date")
        name = item.get("name")
        is_off = item.get("isOffDay")
        if (
            not isinstance(date_value, str)
            or not date_value.startswith(f"{year}-")
            or not isinstance(name, str)
            or not isinstance(is_off, bool)
        ):
            raise ValueError("holiday day has invalid fields")
        result[date_value[5:]] = {"name": name, "isOffDay": is_off}
    return result


async def get_holidays(
    conn: sqlite3.Connection,
    year: int,
    client: httpx.AsyncClient | None = None,
) -> HolidayResult:
    cached = get_holiday_cache(conn, year)
    if cached is not None:
        return HolidayResult(year, cached[0], "cache")

    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=5.0)
    try:
        for template in UPSTREAM_URLS:
            try:
                response = await http_client.get(template.format(year=year))
                response.raise_for_status()
                holidays = _normalize(year, response.json())
            except (httpx.HTTPError, ValueError):
                continue
            fetched_at = (
                datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )
            with conn:
                set_holiday_cache(conn, year, holidays, fetched_at)
            return HolidayResult(year, holidays, "remote")
    finally:
        if owns_client:
            await http_client.aclose()
    return HolidayResult(year, {}, "fallback")
```

- [ ] **Step 4: Add and test the holiday route**

Create `backend/tests/api/test_holidays_api.py`:

```python
from fastapi.testclient import TestClient

from backend.services.holidays import HolidayResult


def test_holiday_endpoint_contract(client: TestClient, monkeypatch) -> None:
    async def fake_get_holidays(conn, year, client=None):
        return HolidayResult(
            year,
            {"01-01": {"name": "元旦", "isOffDay": True}},
            "cache",
        )

    monkeypatch.setattr("backend.api.holidays.get_holidays", fake_get_holidays)
    response = client.get("/api/holidays/2026")
    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "holidays": {
            "01-01": {"name": "元旦", "isOffDay": True}
        },
        "source": "cache",
    }
```

Create `backend/backend/api/holidays.py`:

```python
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
```

Import `holidays` in `backend/backend/main.py` and register:

```python
app.include_router(holidays.router, prefix="/api")
```

- [ ] **Step 5: Run holiday tests**

Run:

```powershell
poetry -C backend run pytest tests/services/test_holidays.py tests/api/test_holidays_api.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Record the checkpoint**

If Git exists:

```powershell
git add backend/backend/services backend/backend/api/holidays.py backend/backend/main.py backend/tests
git commit -m "feat: cache holiday data in sqlite"
```

Otherwise record the passing holiday tests and changed files.

### Task 6: Versioned Transactional Backup API

**Files:**
- Create: `backend/backend/services/backup.py`
- Create: `backend/backend/api/backup.py`
- Modify: `backend/backend/main.py`
- Create: `backend/tests/services/test_backup.py`
- Create: `backend/tests/api/test_backup_api.py`

**Interfaces:**
- Consumes: all Task 3 repositories and Task 4 validation models.
- Produces: `build_backup(conn) -> dict[str, object]`, `restore_backup(conn, raw) -> dict[str, int]`, `GET /api/backup`, and `POST /api/backup`.

- [ ] **Step 1: Write failing compatibility and atomicity tests**

Create `backend/tests/services/test_backup.py`:

```python
from pathlib import Path

import pytest

from backend.db import connect, initialize_database
from backend.repositories.entries import list_entries, upsert_entry
from backend.repositories.preferences import get_theme, set_theme
from backend.services.backup import build_backup, restore_backup


def test_version_1_replaces_only_entries(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    with conn:
        set_theme(conn, "teal")
        upsert_entry(conn, "2026-07-01", "08:00", "18:00", True)

    summary = restore_backup(
        conn,
        {
            "version": 1,
            "exportedAt": "2026-07-12T00:00:00Z",
            "entries": {
                "2026-07-12": {"in": "08:10", "out": "18:40"}
            },
        },
    )

    assert summary == {"version": 1, "entries": 1, "holidayYears": 0}
    assert list_entries(conn) == {
        "2026-07-12": {"in": "08:10", "out": "18:40"}
    }
    assert get_theme(conn) == "teal"
    conn.close()


def test_version_2_round_trip_and_invalid_restore_is_atomic(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    original = build_backup(conn)
    original["entries"] = {
        "2026-07-12": {"in": "08:00", "out": "18:30", "counts": True}
    }
    original["preferences"] = {"theme": "teal"}

    restore_backup(conn, original)
    before_invalid = build_backup(conn)
    bad = {
        **before_invalid,
        "entries": {"2026-07-13": {"in": "18:00", "out": "08:00"}},
    }
    with pytest.raises(ValueError):
        restore_backup(conn, bad)

    assert build_backup(conn)["entries"] == before_invalid["entries"]
    assert build_backup(conn)["preferences"] == {"theme": "teal"}
    conn.close()
```

- [ ] **Step 2: Run tests and verify failure**

Run: `poetry -C backend run pytest tests/services/test_backup.py -v`

Expected: FAIL because `backend.services.backup` does not exist.

- [ ] **Step 3: Implement pre-validation and transactional restore**

Create `backend/backend/services/backup.py`:

```python
import sqlite3
from datetime import datetime, timezone
from typing import Any

from backend.repositories.entries import list_entries, replace_entries
from backend.repositories.holidays import list_holiday_cache, replace_holiday_cache
from backend.repositories.preferences import get_theme, set_theme
from backend.schemas import PreferencesPayload, WorkEntryPayload, validate_work_date


def _validate_entries(raw: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ValueError("entries must be an object")
    validated: dict[str, dict[str, Any]] = {}
    for work_date, value in raw.items():
        if not isinstance(work_date, str):
            raise ValueError("entry date must be a string")
        validate_work_date(work_date)
        payload = WorkEntryPayload.model_validate(value)
        validated[work_date] = payload.model_dump(
            by_alias=True,
            exclude_none=True,
        )
    return validated


def _validate_holiday_cache(raw: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ValueError("holidayCache must be an object")
    validated: dict[str, dict[str, Any]] = {}
    for year, value in raw.items():
        if (
            not isinstance(year, str)
            or not year.isdigit()
            or not isinstance(value, dict)
            or not isinstance(value.get("holidays"), dict)
            or not isinstance(value.get("fetchedAt"), str)
        ):
            raise ValueError("holidayCache entry has invalid fields")
        year_number = int(year)
        if year_number < 2000 or year_number > 2100:
            raise ValueError("holiday cache year must be 2000..2100")
        fetched_at = value["fetchedAt"]
        try:
            datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("holiday fetchedAt must be an ISO timestamp") from exc
        holidays: dict[str, dict[str, str | bool]] = {}
        for month_day, info in value["holidays"].items():
            if not isinstance(month_day, str) or not isinstance(info, dict):
                raise ValueError("holiday entry has invalid fields")
            try:
                datetime.strptime(f"{year}-{month_day}", "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("holiday date must use MM-DD") from exc
            if (
                not isinstance(info.get("name"), str)
                or not isinstance(info.get("isOffDay"), bool)
            ):
                raise ValueError("holiday entry has invalid fields")
            holidays[month_day] = {
                "name": info["name"],
                "isOffDay": info["isOffDay"],
            }
        validated[year] = {
            "holidays": holidays,
            "fetchedAt": fetched_at,
        }
    return validated


def build_backup(conn: sqlite3.Connection) -> dict[str, object]:
    exported_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    return {
        "version": 2,
        "exportedAt": exported_at,
        "entries": list_entries(conn),
        "preferences": {"theme": get_theme(conn)},
        "holidayCache": list_holiday_cache(conn),
    }


def restore_backup(
    conn: sqlite3.Connection,
    raw: object,
) -> dict[str, int]:
    if not isinstance(raw, dict):
        raise ValueError("backup must be an object")
    version = raw.get("version")
    if version not in (1, 2):
        raise ValueError("unsupported backup version")
    exported_at = raw.get("exportedAt")
    if not isinstance(exported_at, str):
        raise ValueError("exportedAt must be an ISO timestamp")
    try:
        datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("exportedAt must be an ISO timestamp") from exc

    entries = _validate_entries(raw.get("entries"))
    if version == 1:
        with conn:
            replace_entries(conn, entries)
        return {"version": 1, "entries": len(entries), "holidayYears": 0}

    preferences = PreferencesPayload.model_validate(raw.get("preferences"))
    holiday_cache = _validate_holiday_cache(raw.get("holidayCache"))
    with conn:
        replace_entries(conn, entries)
        set_theme(conn, preferences.theme)
        replace_holiday_cache(conn, holiday_cache)
    return {
        "version": 2,
        "entries": len(entries),
        "holidayYears": len(holiday_cache),
    }
```

- [ ] **Step 4: Add and test backup routes**

Create `backend/tests/api/test_backup_api.py`:

```python
import json

from fastapi.testclient import TestClient


def test_backup_download_and_legacy_upload(client: TestClient) -> None:
    download = client.get("/api/backup")
    assert download.status_code == 200
    assert download.json()["version"] == 2
    disposition = download.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="workhours-')
    assert disposition.endswith('.json"')

    legacy = {
        "version": 1,
        "exportedAt": "2026-07-12T00:00:00Z",
        "entries": {
            "2026-07-12": {"in": "08:00", "out": "18:30"}
        },
    }
    upload = client.post(
        "/api/backup",
        files={
            "file": (
                "legacy.json",
                json.dumps(legacy).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert upload.status_code == 200
    assert upload.json()["entries"] == 1
```

Create `backend/backend/api/backup.py`:

```python
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
async def upload_backup(
    file: UploadFile,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, int]:
    try:
        raw = json.loads((await file.read()).decode("utf-8"))
        return restore_backup(conn, raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

Import `backup` in `backend/backend/main.py` and register:

```python
app.include_router(backup.router, prefix="/api")
```

- [ ] **Step 5: Run backup and full backend tests**

Run:

```powershell
poetry -C backend run pytest tests/services/test_backup.py tests/api/test_backup_api.py -v
poetry -C backend run pytest -v
```

Expected: backup tests PASS, then the complete backend suite PASS.

- [ ] **Step 6: Record the checkpoint**

If Git exists:

```powershell
git add backend/backend/services/backup.py backend/backend/api/backup.py backend/backend/main.py backend/tests
git commit -m "feat: add transactional database backups"
```

Otherwise record the passing backend suite and changed files.

### Task 7: Typed Frontend API Adapter

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/api.test.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`

**Interfaces:**
- Consumes: Task 4–6 HTTP contracts.
- Produces: `getEntries`, `putEntry`, `deleteEntry`, `getPreferences`, `putPreferences`, `getHolidays`, `downloadBackup`, `importBackup`, and `ApiError`.

- [ ] **Step 1: Install frontend test dependencies inside `frontend/`**

Run:

```powershell
npm --prefix frontend install --save-dev vitest jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom
```

Add `"test": "vitest run"` to `frontend/package.json` without changing the existing build script.

Create `frontend/vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
  },
})
```

Create `frontend/src/test/setup.ts`:

```typescript
import '@testing-library/jest-dom/vitest'

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: () => ({
    matches: true,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }),
})

class ResizeObserverStub {
  constructor(_callback: ResizeObserverCallback) {}
  observe(_target: Element) {}
  unobserve(_target: Element) {}
  disconnect() {}
}

globalThis.ResizeObserver = ResizeObserverStub as typeof ResizeObserver
```

- [ ] **Step 2: Write failing adapter tests**

Add to `frontend/src/lib/types.ts`:

```typescript
export type Theme = 'cool' | 'teal'
export type HolidaySource = 'cache' | 'remote' | 'fallback'
```

Create `frontend/src/lib/api.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getEntries, putEntry } from './api'

describe('api adapter', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('returns entries from the backend', async () => {
    const entries = {
      '2026-07-12': { in: '08:00', out: '18:30', counts: true },
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(entries), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    await expect(getEntries()).resolves.toEqual(entries)
  })

  it('unwraps a saved entry', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          date: '2026-07-12',
          entry: { in: '08:00', out: '18:30', counts: true },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    await expect(
      putEntry('2026-07-12', {
        in: '08:00',
        out: '18:30',
        counts: true,
      }),
    ).resolves.toEqual({ in: '08:00', out: '18:30', counts: true })
  })

  it('exposes backend error detail and status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'database operation failed' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    await expect(getEntries()).rejects.toEqual(
      new ApiError(500, 'database operation failed'),
    )
  })
})
```

- [ ] **Step 3: Run tests and verify failure**

Run: `npm --prefix frontend test -- src/lib/api.test.ts`

Expected: FAIL because `frontend/src/lib/api.ts` does not exist.

- [ ] **Step 4: Implement the HTTP adapter**

Create `frontend/src/lib/api.ts`:

```typescript
import type {
  Entries,
  HolidayMap,
  HolidaySource,
  Theme,
  WorkEntry,
} from './types'

const API_ROOT = import.meta.env.DEV
  ? 'http://127.0.0.1:8000/api'
  : '/api'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API_ROOT + path, init)
  if (!response.ok) {
    let message = '请求失败'
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // Keep the stable fallback for non-JSON errors.
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const getEntries = () => request<Entries>('/entries')

export async function putEntry(
  date: string,
  entry: WorkEntry,
): Promise<WorkEntry> {
  const result = await request<{ date: string; entry: WorkEntry }>(
    '/entries/' + encodeURIComponent(date),
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entry),
    },
  )
  return result.entry
}

export const deleteEntry = (date: string) =>
  request<void>('/entries/' + encodeURIComponent(date), { method: 'DELETE' })

export const getPreferences = () =>
  request<{ theme: Theme }>('/preferences')

export const putPreferences = (theme: Theme) =>
  request<{ theme: Theme }>('/preferences', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme }),
  })

export interface HolidayApiResponse {
  year: number
  holidays: HolidayMap
  source: HolidaySource
}

export const getHolidays = (year: number) =>
  request<HolidayApiResponse>('/holidays/' + year)

export function downloadBackup(): void {
  const anchor = document.createElement('a')
  anchor.href = API_ROOT + '/backup'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

export function importBackup(file: File): Promise<{
  version: number
  entries: number
  holidayYears: number
}> {
  const body = new FormData()
  body.append('file', file)
  return request('/backup', { method: 'POST', body })
}
```

- [ ] **Step 5: Run adapter tests and the frontend build**

Run:

```powershell
npm --prefix frontend test -- src/lib/api.test.ts
npm --prefix frontend run build
```

Expected: 3 adapter tests PASS and the frontend build PASS.

- [ ] **Step 6: Record the checkpoint**

If Git exists:

```powershell
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/src
git commit -m "feat: add typed backend api client"
```

Otherwise record the passing test/build output and changed files.

### Task 8: Replace Browser Persistence in React

**Files:**
- Create: `frontend/src/App.test.tsx`
- Create: `frontend/src/components/EntryModal.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Header.tsx`
- Modify: `frontend/src/components/EntryModal.tsx`
- Modify: `frontend/src/lib/holidays.ts`
- Modify: `frontend/src/lib/useTheme.ts`
- Delete: `frontend/src/lib/storage.ts`
- Delete: `frontend/src/lib/backup.ts`

**Interfaces:**
- Consumes: all Task 7 API functions and the existing `Entries`/`HolidayMap` component contracts.
- Produces: server-loaded App state, controlled theme props, asynchronous modal actions, and no browser persistence.

- [ ] **Step 1: Write failing bootstrap and failed-save tests**

Create `frontend/src/App.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './lib/api'

vi.mock('./lib/api')

beforeEach(() => {
  vi.mocked(api.getEntries).mockResolvedValue({})
  vi.mocked(api.getPreferences).mockResolvedValue({ theme: 'teal' })
  vi.mocked(api.getHolidays).mockResolvedValue({
    year: new Date().getFullYear(),
    holidays: {},
    source: 'cache',
  })
})

it('loads all persistent state from the backend before showing the app', async () => {
  render(<App />)

  expect(screen.getByText('正在连接本地数据库…')).toBeInTheDocument()
  expect(await screen.findByText('Workhours')).toBeInTheDocument()
  expect(api.getEntries).toHaveBeenCalledOnce()
  expect(api.getPreferences).toHaveBeenCalledOnce()
  expect(api.getHolidays).toHaveBeenCalled()
  expect(document.documentElement).toHaveAttribute('data-theme', 'teal')
})
```

Create `frontend/src/components/EntryModal.test.tsx`:

```typescript
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import EntryModal from './EntryModal'

it('keeps the modal and input visible when the backend save fails', async () => {
  const onSave = vi.fn().mockRejectedValue(new Error('数据库写入失败'))
  render(
    <EntryModal
      date="2026-07-12"
      entry={{ in: '08:00', out: '18:30', counts: true }}
      isRestDay={false}
      onClose={vi.fn()}
      onSave={onSave}
      onDelete={vi.fn()}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: '保存' }))

  expect(await screen.findByText('数据库写入失败')).toBeInTheDocument()
  expect(screen.getByText('2026-07-12')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run UI tests and verify failure**

Run:

```powershell
npm --prefix frontend test -- src/App.test.tsx src/components/EntryModal.test.tsx
```

Expected: FAIL because App still reads localStorage and modal callbacks are synchronous.

- [ ] **Step 3: Make theme application controlled by server state**

Replace `frontend/src/lib/useTheme.ts` with:

```typescript
import { useLayoutEffect } from 'react'
import type { Theme } from './types'

export function useAppliedTheme(theme: Theme | null): void {
  useLayoutEffect(() => {
    if (theme === null) return
    const root = document.documentElement
    if (theme === 'cool') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
  }, [theme])
}
```

In `frontend/src/components/Header.tsx`:

- Remove the `useTheme` import and hook call.
- Add `theme: Theme`, `themeBusy: boolean`, and `onThemeToggle: () => void` to `Props`.
- Destructure those props.
- Change the theme button to `onClick={onThemeToggle}` while preserving its current label expression.
- Add `disabled={themeBusy}` to the theme button so repeated writes cannot overlap.
- Keep `onExport` and `onImport` controlled by App.

The exact new prop fragment is:

```typescript
import type { Theme } from '../lib/types'

interface Props {
  y: number
  m: number
  theme: Theme
  themeBusy: boolean
  onPrev: () => void
  onNext: () => void
  onToday: () => void
  onThemeToggle: () => void
  onExport: () => void
  onImport: (file: File) => void
}
```

- [ ] **Step 4: Convert EntryModal actions to server-confirmed promises**

Change its callback props and add action state:

```typescript
interface Props {
  date: string
  entry?: WorkEntry
  isRestDay: boolean
  onClose: () => void
  onSave: (e: WorkEntry) => Promise<void>
  onDelete: () => Promise<void>
}

const [busy, setBusy] = useState(false)
const [actionError, setActionError] = useState('')

const runAction = async (action: () => Promise<void>) => {
  setBusy(true)
  setActionError('')
  try {
    await action()
  } catch (error) {
    setActionError(error instanceof Error ? error.message : String(error))
  } finally {
    setBusy(false)
  }
}

const handleSave = () => {
  if (!valid || busy) return
  void runAction(() => onSave({ in: i, out: o, counts }))
}

const handleDelete = () => {
  if (busy) return
  void runAction(onDelete)
}
```

Render `actionError` beside the existing validation error, call `handleDelete` from the delete button, and disable save, delete, cancel, and backdrop close while `busy` is true. Use button text `保存中…` while saving. Do not clear or close the modal in the error branch.

- [ ] **Step 5: Replace App persistence with API bootstrap and confirmed writes**

In `frontend/src/App.tsx`:

1. Remove imports from `storage` and `backup` and remove `fetchHolidays`.
2. Import `Theme`/`HolidaySource`, `useAppliedTheme`, and all required API functions.
3. Initialize entries to `{}` rather than loading localStorage.
4. Add the following state and effects:

```typescript
const [entries, setEntries] = useState<Entries>({})
const [hMap, setHMap] = useState<HolidayMap | undefined>(undefined)
const [holidaySource, setHolidaySource] = useState<HolidaySource | null>(null)
const [theme, setTheme] = useState<Theme | null>(null)
const [themeBusy, setThemeBusy] = useState(false)
const [loading, setLoading] = useState(true)
const [loadError, setLoadError] = useState('')

useAppliedTheme(theme)

useEffect(() => {
  let alive = true
  Promise.all([getEntries(), getPreferences()])
    .then(([loadedEntries, preferences]) => {
      if (!alive) return
      setEntries(loadedEntries)
      setTheme(preferences.theme)
      setLoading(false)
    })
    .catch((error) => {
      if (!alive) return
      setLoadError(error instanceof Error ? error.message : String(error))
      setLoading(false)
    })
  return () => {
    alive = false
  }
}, [])

useEffect(() => {
  let alive = true
  setHMap(undefined)
  setHolidaySource(null)
  getHolidays(viewY)
    .then((result) => {
      if (!alive) return
      setHMap(result.holidays)
      setHolidaySource(result.source)
    })
    .catch((error) => {
      if (!alive) return
      setLoadError(error instanceof Error ? error.message : String(error))
    })
  return () => {
    alive = false
  }
}, [viewY])
```

Before the existing main UI, return a loading or blocking connection state:

```tsx
if (loadError) {
  return (
    <div className="min-h-screen grid place-items-center text-plum">
      无法连接本地数据库：{loadError}
    </div>
  )
}
if (loading || theme === null) {
  return <div className="min-h-screen grid place-items-center">正在连接本地数据库…</div>
}
```

Replace `upsert` with:

```typescript
const upsert = async (date: string, entry: WorkEntry | null) => {
  if (entry) {
    const saved = await putEntry(date, entry)
    setEntries((prev) => ({ ...prev, [date]: saved }))
  } else {
    await deleteEntry(date)
    setEntries((prev) => {
      const next = { ...prev }
      delete next[date]
      return next
    })
  }
}
```

Use exact server-confirmed handlers:

```typescript
const handleThemeToggle = async () => {
  if (themeBusy) return
  const nextTheme: Theme = theme === 'cool' ? 'teal' : 'cool'
  setThemeBusy(true)
  try {
    const saved = await putPreferences(nextTheme)
    setTheme(saved.theme)
  } catch (error) {
    window.alert('主题保存失败：' + (error instanceof Error ? error.message : String(error)))
  } finally {
    setThemeBusy(false)
  }
}

const handleExport = () => downloadBackup()

const handleImport = async (file: File) => {
  if (
    Object.keys(entries).length > 0 &&
    !window.confirm('导入会覆盖数据库中的现有数据，确定？')
  ) return
  try {
    const summary = await importBackup(file)
    const [loadedEntries, preferences, holidays] = await Promise.all([
      getEntries(),
      getPreferences(),
      getHolidays(viewY),
    ])
    setEntries(loadedEntries)
    setTheme(preferences.theme)
    setHMap(holidays.holidays)
    setHolidaySource(holidays.source)
    window.alert('导入成功，共 ' + summary.entries + ' 条记录')
  } catch (error) {
    window.alert('导入失败：' + (error instanceof Error ? error.message : String(error)))
  }
}
```

Import `WorkEntry` together with `Theme` and `HolidaySource`. Pass `theme`, `themeBusy`, and `onThemeToggle={handleThemeToggle}` to Header. Make modal callbacks `async`, await `upsert`, and only then set `modalDate` to `null`. Build the footer note from `holidaySource`; `fallback` must retain the current “按周末推断” warning.

- [ ] **Step 6: Remove browser persistence and direct holiday HTTP**

In `frontend/src/lib/holidays.ts`:

- Delete imports from `storage`.
- Delete `holidayMem` and the complete `fetchHolidays` function.
- Keep `dayInfo` and `workingDaysInMonth` unchanged.

Delete `frontend/src/lib/storage.ts` and `frontend/src/lib/backup.ts` after `rg` confirms no remaining imports:

```powershell
rg -n "from './lib/(storage|backup)'|from '../lib/(storage|backup)'|fetchHolidays|localStorage" frontend/src
```

Expected before deletion: no production references except the files being deleted. Expected after deletion: no matches for formal data persistence; comments that intentionally say “no localStorage” may remain.

- [ ] **Step 7: Run UI tests and full frontend validation**

Run:

```powershell
npm --prefix frontend test
npm --prefix frontend run build
```

Expected: all Vitest tests PASS and TypeScript/Vite build PASS.

- [ ] **Step 8: Record the checkpoint**

If Git exists:

```powershell
git add frontend/src frontend/package.json frontend/package-lock.json frontend/vitest.config.ts
git commit -m "feat: move frontend persistence to api"
```

Otherwise record the passing frontend test/build output and changed/deleted files.

### Task 9: Serve the Built App, Update Docs, and Verify End to End

**Files:**
- Modify: `backend/backend/main.py`
- Create: `backend/tests/api/test_frontend.py`
- Modify: `README.md`
- Modify: `doc/backend/业务规则/数据存储与备份.md`
- Create: `doc/backend/项目日志/2026-07-12-本地后端与数据库.md`

**Interfaces:**
- Consumes: complete backend API and built `frontend/dist/index.html`.
- Produces: `GET /` serving the single-file frontend, final operator instructions, and end-to-end evidence.

- [ ] **Step 1: Write the failing frontend-serving test**

Create `backend/tests/api/test_frontend.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app


def test_root_serves_built_single_file(tmp_path: Path) -> None:
    frontend_dir = tmp_path / "dist"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text(
        "<!doctype html><title>Workhours</title>",
        encoding="utf-8",
    )
    app = create_app(tmp_path / "test.db", frontend_dir=frontend_dir)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Workhours" in response.text


def test_missing_build_returns_clear_503(tmp_path: Path) -> None:
    app = create_app(
        tmp_path / "test.db",
        frontend_dir=tmp_path / "missing-dist",
    )

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "frontend build not found; run npm --prefix frontend run build"
    }
```

- [ ] **Step 2: Run the test and verify failure**

Run: `poetry -C backend run pytest tests/api/test_frontend.py -v`

Expected: FAIL with `404 Not Found` because `GET /` is not registered.

- [ ] **Step 3: Serve `frontend/dist/index.html` from the default app**

In `backend/backend/main.py`:

1. Import `FileResponse` and `HTTPException`.
2. Define `BACKEND_ROOT = Path(__file__).resolve().parents[1]`, `REPOSITORY_ROOT = BACKEND_ROOT.parent`, and `DEFAULT_FRONTEND_DIR = REPOSITORY_ROOT / "frontend" / "dist"`.
3. Change the factory default to `frontend_dir: Path | None = DEFAULT_FRONTEND_DIR`.
4. Register this route after all `/api` routers:

```python
@app.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    if app.state.frontend_dir is None:
        raise HTTPException(
            status_code=503,
            detail="frontend build not found; run npm --prefix frontend run build",
        )
    index_path = Path(app.state.frontend_dir) / "index.html"
    if not index_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="frontend build not found; run npm --prefix frontend run build",
        )
    return FileResponse(index_path)
```

Keep `app = create_app()` so the fixed startup command remains:

```powershell
poetry -C backend run uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 4: Run backend, frontend, and static-serving tests**

Run:

```powershell
poetry -C backend run pytest -v
npm --prefix frontend test
npm --prefix frontend run build
poetry -C backend run pytest tests/api/test_frontend.py -v
```

Expected: all four commands PASS.

- [ ] **Step 5: Update authoritative documentation**

Update `README.md` to state:

- Data now lives in `backend/data/workhours.db`, not localStorage.
- Run `poetry -C backend install` and `npm --prefix frontend install` once.
- Build with `npm --prefix frontend run build`.
- Start with `poetry -C backend run uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
- Open `http://127.0.0.1:8000` instead of double-clicking `frontend/dist/index.html`.
- Legacy version 1 JSON imports only entries; version 2 backs up entries, theme, and holiday cache.
- Never use global `pip install` for this project.

Replace the browser-storage statements in `doc/backend/业务规则/数据存储与备份.md` with the approved SQLite, API, backup-version, transaction, and Poetry rules. Preserve the browser download-location limitation only where it still applies to manual backup downloads.

Create `doc/backend/项目日志/2026-07-12-本地后端与数据库.md` using the existing project-log conventions. Record the selected architecture, files changed, legacy migration behavior, test commands, and observed pass counts. Do not claim a browser check until it has actually run.

- [ ] **Step 6: Perform the real local acceptance test**

Run the server in a hidden background process:

```powershell
Start-Process -FilePath "poetry" -ArgumentList @(
  "-C", "backend", "run", "uvicorn", "backend.main:app",
  "--host", "127.0.0.1", "--port", "8000"
) -WorkingDirectory (Get-Location) -WindowStyle Hidden
```

Then verify:

1. Open `http://127.0.0.1:8000` in a real browser.
2. Create and edit one date, refresh, and confirm persistence.
3. Change theme, restart the browser page, and confirm persistence.
4. Stop and restart Uvicorn, then confirm both values still exist.
5. Import `backend/data/workhours-2026-07-12.json` as legacy version 1 and confirm entries appear without resetting theme.
6. Export version 2, modify data, import the exported file, and confirm all three data categories restore.
7. Stop Uvicorn and attempt a save; confirm the modal stays open with an error and no localStorage keys are created.
8. Temporarily simulate holiday network failure only through a test/mocked path; do not disrupt the user's real network settings.

Inspect browser localStorage and confirm these keys are absent:

```text
workhours_v1
workhours_theme_v1
holidaycn_v1_<year>
```

- [ ] **Step 7: Run final verification from a clean command sequence**

Run:

```powershell
poetry -C backend env info --path
poetry -C backend run pytest -v
npm --prefix frontend test
npm --prefix frontend run build
rg -n "workhours_v1|workhours_theme_v1|holidaycn_v1_|localStorage" frontend/src
```

Expected:

- Poetry environment path is the project `backend/.venv`.
- All backend and frontend tests PASS.
- TypeScript/Vite build PASS.
- `rg` finds no production persistence use. A deliberate assertion in a test is acceptable only if it verifies that the keys are absent.

- [ ] **Step 8: Record the final checkpoint**

If Git exists:

```powershell
git add backend frontend .gitignore README.md AGENTS.md doc
git commit -m "feat: add local database-backed application"
```

Otherwise provide the complete changed-file list and the exact final verification output; do not initialize Git.
