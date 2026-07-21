# Arbitrary Entry Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users view, add, and modify work entries for any date, then recalculate the relevant weekly or monthly forecast immediately after saving.

**Architecture:** Keep SQLite persistence unchanged because entries already upsert by date. Add a dashboard reference date in the Flask layer, preserve it across forms, and update the template so both the focused date form and each period table row can save entries.

**Tech Stack:** Python 3.11, Flask, SQLite, pytest, Poetry.

---

### Task 1: Web Behavior Tests

**Files:**
- Modify: `tests/test_web.py`

- [ ] Add tests for `/?reference_date=YYYY-MM-DD` showing the selected date's period.
- [ ] Add tests for saving a past entry and redirecting to that date's period.
- [ ] Add tests for updating an existing past entry and seeing recalculated effective hours.
- [ ] Add tests that the prediction table exposes editable fields for period workdays.

### Task 2: Reference-Date Routing

**Files:**
- Modify: `src/workhours/web.py`

- [ ] Parse optional `reference_date` from query string.
- [ ] Build forecasts around the selected reference date instead of always today.
- [ ] Redirect entry saves, settings changes, calendar changes, and quick clock actions with the correct reference date.
- [ ] Provide `selected_date` and `selected_entry` to the template.

### Task 3: Editable Dashboard

**Files:**
- Modify: `src/workhours/templates/index.html`
- Modify: `src/workhours/static/styles.css`

- [ ] Add a date focus form for jumping to any date.
- [ ] Make the work entry form use the selected date and selected entry.
- [ ] Add inline start/end inputs and save buttons to each workday row in the prediction table.
- [ ] Keep quick clock-in/out focused on today's real date.

### Task 4: Verification

**Files:**
- Modify: none unless verification finds issues.

- [ ] Run `poetry run pytest -v`.
- [ ] Run `poetry check`.
- [ ] Restart the local Flask server.
- [ ] Verify `http://127.0.0.1:5000/?reference_date=2026-07-01` returns the dashboard content.
