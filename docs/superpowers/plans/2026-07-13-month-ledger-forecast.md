# Month-Ledger Forecast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make monthly average time authoritative while weekly mode carries only the selected month's earlier balance and catches it up within the clipped week.

**Architecture:** Keep calculations in `domain.py`, persistence in `storage.py`, and request/rendering work in `web.py`. `build_forecast` will create a monthly ledger first, then derive either a full-month planning horizon or a week clipped to that month. Missing past records receive a transparent neutral 9-hour planning credit until the user fills them.

**Tech Stack:** Python 3.11+, Flask, SQLite, Jinja, pytest, Poetry.

## Global Constraints

- Natural calendar months are independent settlement periods.
- Target effective time is 540 minutes per adjusted workday.
- Minimum recommendation is 480 minutes per normal workday.
- Default lunch is 90 minutes and is excluded from effective work time.
- Calendar overrides determine holidays and adjusted workdays.
- No SQLite migration is required.

---

### Task 1: Month-Owned Domain Forecast

**Files:**
- Modify: `tests/test_domain.py`
- Modify: `src/workhours/domain.py`

**Interfaces:**
- Consumes: `build_forecast(reference_date, entries, overrides, settings)`.
- Produces: `Forecast.base_target_minutes`, `Forecast.carryover_minutes`, `Forecast.month_target_minutes`, `Forecast.month_completed_minutes`, and `Forecast.missing_history_days`.

- [ ] **Step 1: Add failing domain tests**

Add tests that assert:

```python
assert forecast.carryover_minutes == 8 * 60
assert forecast.target_minutes == 53 * 60
assert forecast.days[date(2026, 7, 13)].recommended_minutes == 10 * 60 + 36
```

Also cover an 8-hour minimum after prior surplus, month distribution through month end, first-week reset, cross-month clipping, and missing past records receiving neutral 9-hour credit.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `poetry run pytest tests/test_domain.py -v`

Expected: failures because the new forecast fields and month-owned behavior do not exist.

- [ ] **Step 3: Implement month bounds and planning horizons**

Keep `period_bounds` public, but clip weekly bounds to the reference month. Build full monthly workdays first, then choose the visible workdays from either the month or clipped week.

- [ ] **Step 4: Implement signed weekly carry and monthly distribution**

Use these formulas:

```python
carryover = prior_target - prior_accounted_minutes
weekly_target = max(base_week_target + carryover, 0)
remaining_target = max(mode_target - mode_accounted_minutes, 0)
```

Past incomplete workdays contribute `target_minutes_per_day` to accounted planning time and are exposed through `missing_history_days`. Only incomplete workdays on or after `reference_date` receive recommendations.

- [ ] **Step 5: Run domain tests and verify GREEN**

Run: `poetry run pytest tests/test_domain.py -v`

Expected: all domain tests pass.

### Task 2: Month Query And Dashboard Presentation

**Files:**
- Modify: `tests/test_web.py`
- Modify: `src/workhours/web.py`
- Modify: `src/workhours/templates/index.html`
- Modify: `src/workhours/static/styles.css`

**Interfaces:**
- Consumes: the new `Forecast` monthly summary and carry fields.
- Produces: a dashboard that always loads the selected month, clips weekly rows, emphasizes monthly progress, and warns about neutral historical assumptions.

- [ ] **Step 1: Add failing Web tests**

Assert that a July 1 weekly view displays `2026-07-01` through `2026-07-05`, does not display June workday rows, shows monthly summary labels, renders signed carry, and displays the missing-history warning when needed.

- [ ] **Step 2: Run Web tests and verify RED**

Run: `poetry run pytest tests/test_web.py -v`

Expected: failures because the dashboard still queries only the old period and lacks the monthly summary.

- [ ] **Step 3: Load the full month in the Web layer**

In `_build_dashboard`, query entries and overrides with monthly bounds regardless of selected mode, then pass them to `build_forecast`.

- [ ] **Step 4: Render monthly progress and weekly carry**

Update the summary to show month target, month recorded time, and current remaining recommendation. In weekly mode, render base week target, signed earlier-month balance, and adjusted target. Add a warning listing missing historical dates and explaining the temporary 9-hour neutral credit.

- [ ] **Step 5: Run Web tests and verify GREEN**

Run: `poetry run pytest tests/test_web.py -v`

Expected: all Web tests pass.

### Task 3: Full Verification And Review

**Files:**
- Verify all modified files.

**Interfaces:**
- Consumes: completed domain and Web changes.
- Produces: verified project behavior with no persistence regression.

- [ ] **Step 1: Run the full test suite**

Run: `poetry run pytest -v`

Expected: all tests pass with no warnings.

- [ ] **Step 2: Validate Poetry metadata**

Run: `poetry check`

Expected: `All set!`.

- [ ] **Step 3: Exercise the local HTTP dashboard**

Start the app and request weekly and monthly URLs for July 2026. Confirm status 200, clipped weekly dates, monthly summary text, and editable entry forms.

- [ ] **Step 4: Review requirements against the diff**

Check month ownership, signed carry, 8-hour minimum, 90-minute lunch, overrides, missing-history behavior, arbitrary-date recalculation, and unchanged SQLite schema.
