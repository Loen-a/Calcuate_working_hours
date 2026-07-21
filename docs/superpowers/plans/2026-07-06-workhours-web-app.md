# Workhours Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python web app that tracks work entries, adjusted workdays, and predicts work duration for weekly or monthly average targets.

**Architecture:** The app separates pure calculation logic from persistence and presentation. `domain.py` owns calendar and forecast rules, `storage.py` owns SQLite access, and `web.py` connects forms, routes, and templates.

**Tech Stack:** Python 3.11+, Poetry, Flask, SQLite, pytest.

---

## File Structure

- `pyproject.toml`: Poetry project metadata, dependencies, scripts, pytest config.
- `src/workhours/__init__.py`: package marker.
- `src/workhours/domain.py`: dataclasses and pure workhour forecast functions.
- `src/workhours/storage.py`: SQLite schema and repository-style functions.
- `src/workhours/web.py`: Flask app factory, routes, form handling, server entry point.
- `src/workhours/templates/index.html`: main dashboard.
- `src/workhours/static/styles.css`: dashboard styles.
- `tests/test_domain.py`: calendar and forecast tests.
- `tests/test_storage.py`: SQLite persistence tests.
- `tests/test_web.py`: route smoke tests.

## Tasks

### Task 1: Project Scaffold And Failing Domain Tests

**Files:**
- Create: `pyproject.toml`
- Create: `src/workhours/__init__.py`
- Create: `tests/test_domain.py`

- [ ] **Step 1: Create Poetry metadata**

```toml
[tool.poetry]
name = "calculate-working-hours"
version = "0.1.0"
description = "Local web app for predicting weekly or monthly average working hours."
authors = ["Local User <local@example.com>"]
readme = "README.md"
packages = [{ include = "workhours", from = "src" }]

[tool.poetry.dependencies]
python = ">=3.11,<4.0"
flask = "^3.0.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"

[tool.poetry.scripts]
workhours-web = "workhours.web:main"

[build-system]
requires = ["poetry-core>=1.8.0"]
build-backend = "poetry.core.masonry.api"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Write failing tests for calendar and forecast rules**

```python
from datetime import date, time

from workhours.domain import (
    DayOverride,
    ForecastSettings,
    PeriodMode,
    WorkEntry,
    build_forecast,
    is_workday,
    period_workdays,
)


def test_calendar_overrides_default_weekday_rules():
    overrides = {
        date(2026, 7, 1): DayOverride.HOLIDAY,
        date(2026, 7, 4): DayOverride.WORKDAY,
    }

    assert is_workday(date(2026, 7, 1), overrides) is False
    assert is_workday(date(2026, 7, 4), overrides) is True
    assert is_workday(date(2026, 7, 6), overrides) is True
    assert is_workday(date(2026, 7, 5), overrides) is False


def test_month_period_uses_adjusted_workdays():
    overrides = {
        date(2026, 7, 1): DayOverride.HOLIDAY,
        date(2026, 7, 4): DayOverride.WORKDAY,
    }

    days = period_workdays(date(2026, 7, 6), PeriodMode.MONTH, overrides)

    assert date(2026, 7, 1) not in days
    assert date(2026, 7, 4) in days
    assert date(2026, 7, 6) in days


def test_forecast_uses_minimum_day_when_remaining_average_is_lower():
    entries = {
        date(2026, 7, 6): WorkEntry(date(2026, 7, 6), time(9), time(20, 30)),
        date(2026, 7, 7): WorkEntry(date(2026, 7, 7), time(9), time(20, 30)),
        date(2026, 7, 8): WorkEntry(date(2026, 7, 8), time(9), time(20, 30)),
        date(2026, 7, 9): WorkEntry(date(2026, 7, 9), time(9), time(20, 30)),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 10),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    today = forecast.days[date(2026, 7, 10)]
    assert forecast.target_minutes == 45 * 60
    assert forecast.completed_minutes == 40 * 60
    assert today.recommended_minutes == 8 * 60
    assert today.reason == "minimum_day"


def test_forecast_marks_goal_met_but_still_recommends_minimum_workday():
    entries = {
        date(2026, 7, 6): WorkEntry(date(2026, 7, 6), time(9), time(22, 30)),
        date(2026, 7, 7): WorkEntry(date(2026, 7, 7), time(9), time(22, 30)),
        date(2026, 7, 8): WorkEntry(date(2026, 7, 8), time(9), time(22, 30)),
        date(2026, 7, 9): WorkEntry(date(2026, 7, 9), time(9), time(22, 30)),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 10),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    assert forecast.goal_met is True
    assert forecast.days[date(2026, 7, 10)].recommended_minutes == 8 * 60
    assert forecast.days[date(2026, 7, 10)].reason == "goal_met_minimum"


def test_open_entry_gets_suggested_end_time_with_lunch_excluded():
    entries = {
        date(2026, 7, 6): WorkEntry(date(2026, 7, 6), time(9, 30), None),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 6),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    assert forecast.days[date(2026, 7, 6)].recommended_minutes == 9 * 60
    assert forecast.days[date(2026, 7, 6)].suggested_end == time(20, 0)
```

- [ ] **Step 3: Run domain tests and verify RED**

Run: `poetry run pytest tests/test_domain.py -v`

Expected: fail because `workhours.domain` is not implemented.

### Task 2: Domain Implementation

**Files:**
- Create: `src/workhours/domain.py`
- Test: `tests/test_domain.py`

- [ ] **Step 1: Implement dataclasses and pure functions**

Implement `DayOverride`, `PeriodMode`, `ForecastSettings`, `WorkEntry`, `DayForecast`, `Forecast`, `is_workday`, `period_workdays`, and `build_forecast`.

- [ ] **Step 2: Run domain tests and verify GREEN**

Run: `poetry run pytest tests/test_domain.py -v`

Expected: all domain tests pass.

### Task 3: SQLite Persistence

**Files:**
- Create: `src/workhours/storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Tests cover settings, entries, and calendar overrides persisted in a temporary SQLite database.

- [ ] **Step 2: Run storage tests and verify RED**

Run: `poetry run pytest tests/test_storage.py -v`

Expected: fail because `workhours.storage` is not implemented.

- [ ] **Step 3: Implement SQLite store**

Implement schema initialization, settings reads/writes, entry upserts, override upserts/deletes, and list methods.

- [ ] **Step 4: Run storage tests and verify GREEN**

Run: `poetry run pytest tests/test_storage.py -v`

Expected: all storage tests pass.

### Task 4: Flask Web App

**Files:**
- Create: `src/workhours/web.py`
- Create: `src/workhours/templates/index.html`
- Create: `src/workhours/static/styles.css`
- Create: `tests/test_web.py`

- [ ] **Step 1: Write failing web tests**

Tests cover dashboard loading, settings update, calendar override creation, and entry creation.

- [ ] **Step 2: Run web tests and verify RED**

Run: `poetry run pytest tests/test_web.py -v`

Expected: fail because `workhours.web` is not implemented.

- [ ] **Step 3: Implement Flask routes and templates**

Implement `create_app`, dashboard route, settings form, work entry form, quick clock-in/clock-out actions, calendar override forms, and app runner.

- [ ] **Step 4: Run web tests and verify GREEN**

Run: `poetry run pytest tests/test_web.py -v`

Expected: all web tests pass.

### Task 5: Full Verification And Local Browser Check

**Files:**
- Modify: none unless verification finds issues.

- [ ] **Step 1: Run the full test suite**

Run: `poetry run pytest -v`

Expected: all tests pass.

- [ ] **Step 2: Start the local app**

Run: `poetry run workhours-web`

Expected: Flask serves the app at `http://127.0.0.1:5000`.

- [ ] **Step 3: Open the app in the browser plugin**

Open: `http://127.0.0.1:5000`

Expected: dashboard displays current cycle, progress, prediction table, settings, entry, and calendar forms without overlapping text.
