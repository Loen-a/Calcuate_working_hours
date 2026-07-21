# Configurable Non-Working Intervals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed lunch deduction with editable recurring non-working intervals shared by actual-time and suggested-end calculations.

**Architecture:** Add a domain value object and interval-aware time arithmetic in `domain.py`, persist rules in a dedicated SQLite table in `storage.py`, and add CRUD routes and an editable settings section through `web.py` and the existing dashboard template. Existing entry rows remain unchanged and are recalculated from current rules on every request.

**Tech Stack:** Python 3.11+, Flask, SQLite, Jinja, pytest, Poetry.

## Global Constraints

- Default enabled intervals are 12:00-13:30 and 19:30-20:00.
- Time after 20:00 counts again.
- Enabled overlaps are merged and deducted once.
- Interval names are non-empty and start time is earlier than end time.
- Rules are global recurring daily settings.
- Existing SQLite entry rows and the `lunch_minutes` column remain compatible.

---

### Task 1: Interval-Aware Domain Arithmetic

**Files:**
- Create: `tests/test_non_working_intervals_domain.py`
- Modify: `src/workhours/domain.py`

**Interfaces:**
- Produces: `NonWorkingInterval`, `default_non_working_intervals()`, interval-aware `effective_minutes`, and interval-aware `_suggested_end`.
- Consumes: `ForecastSettings.non_working_intervals` in all forecast calculations.

- [ ] **Step 1: Write failing tests**

Add real examples asserting 09:00-20:30 equals 570 minutes, 13:30-19:45 equals 360 minutes, overlapping rules deduct once, 20:00-21:00 equals 60 minutes, and a 10-hour recommendation from 09:00 suggests 21:00.

- [ ] **Step 2: Verify RED**

Run: `poetry run pytest tests/test_non_working_intervals_domain.py -v`

Expected: failures because `NonWorkingInterval` and interval-aware calculations do not exist.

- [ ] **Step 3: Implement minimal domain behavior**

Add the value object, default tuple, overlap-union helper, recurring daily overlap calculation, and timeline advancement for suggested clock-out time. Keep `WorkEntry.lunch_minutes` for compatibility but do not use it when rules are provided through settings.

- [ ] **Step 4: Verify GREEN and regressions**

Run: `poetry run pytest tests/test_non_working_intervals_domain.py tests/test_domain.py tests/test_month_ledger.py -v`

Expected: all selected tests pass after updating old examples to the new default evening break.

### Task 2: SQLite Rule Persistence

**Files:**
- Create: `tests/test_non_working_intervals_storage.py`
- Modify: `src/workhours/storage.py`

**Interfaces:**
- Produces: `list_non_working_intervals()`, `save_non_working_interval(rule)`, and `delete_non_working_interval(rule_id)`.
- Updates: `get_settings()` to return stored rules.

- [ ] **Step 1: Write failing storage tests**

Assert one-time default seeding, add/update/disable/delete persistence, stable ids, and no reseeding after all rules are deleted.

- [ ] **Step 2: Verify RED**

Run: `poetry run pytest tests/test_non_working_intervals_storage.py -v`

Expected: failures because the table and methods do not exist.

- [ ] **Step 3: Implement schema and CRUD**

Create `non_working_intervals`, seed defaults behind a settings marker, map rows to domain objects, and include the rules in `ForecastSettings`.

- [ ] **Step 4: Verify GREEN and storage regression**

Run: `poetry run pytest tests/test_non_working_intervals_storage.py tests/test_storage.py -v`

Expected: all storage tests pass.

### Task 3: Web CRUD And Dashboard UI

**Files:**
- Create: `tests/test_non_working_intervals_web.py`
- Modify: `src/workhours/web.py`
- Modify: `src/workhours/templates/index.html`
- Modify: `src/workhours/static/styles.css`

**Interfaces:**
- Produces: POST save/delete routes and dashboard context for editable rules.
- Consumes: storage CRUD and `ForecastSettings.non_working_intervals`.

- [ ] **Step 1: Write failing Web tests**

Assert default rows render, valid rules can be added/edited/disabled/deleted, invalid ranges are rejected without persistence, the selected date survives redirects, and changing a rule recalculates an existing entry.

- [ ] **Step 2: Verify RED**

Run: `poetry run pytest tests/test_non_working_intervals_web.py -v`

Expected: failures because routes and controls do not exist.

- [ ] **Step 3: Implement routes and validation**

Parse ids, names, times, and enabled state. Reject empty names and `start >= end` with a flash message, otherwise upsert and redirect to the current reference date.

- [ ] **Step 4: Implement the editable section**

Render add and inline-edit forms with stable form ids, checkbox controls, save/delete buttons, and responsive grid constraints. Replace the fixed lunch header copy with the enabled rule count.

- [ ] **Step 5: Verify GREEN and Web regressions**

Run: `poetry run pytest tests/test_non_working_intervals_web.py tests/test_web.py tests/test_month_ledger_web.py -v`

Expected: all Web tests pass after updating expected effective-time strings.

### Task 4: Full Verification And Review

**Files:**
- Verify all modified files and the written specification.

**Interfaces:**
- Produces: verified local Web behavior with the existing database upgraded in place.

- [ ] **Step 1: Run the complete test suite**

Run: `poetry run pytest -v`

Expected: all tests pass.

- [ ] **Step 2: Validate Poetry metadata**

Run: `poetry check`

Expected: `All set!`.

- [ ] **Step 3: Perform independent read-only code review**

Review domain overlap arithmetic, overnight handling, one-time default seeding, validation, CRUD behavior, and UI form structure against the specification.

- [ ] **Step 4: Start the updated background server and exercise HTTP**

Request the dashboard, add and edit a rule in an isolated temporary database, verify recalculated effective time, and leave the updated app running on a free local port.
