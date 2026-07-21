# Cumulative Monthly Balance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the suggested-end table column with a per-workday cumulative monthly balance against the 540-minute target.

**Architecture:** Compute daily and running balances inside `build_forecast()` from the already-loaded natural-month workdays. Store display values on `DayForecast`; render them in the existing table without adding persistence or changing suggested-end domain behavior.

**Tech Stack:** Python 3.11, Flask, Jinja, SQLite, pytest, Poetry.

## Global Constraints

- Natural-month balance starts at zero and never carries across months.
- Only complete records on effective workdays contribute.
- Weekly views include earlier workdays from the same month.
- Missing/open entries display `-` and contribute nothing.
- Existing non-working interval calculations remain authoritative.
- The workspace is not a Git repository, so verification replaces commit steps.

---

### Task 1: Domain Balance Ledger

**Files:**
- Modify: `src/workhours/domain.py`
- Create: `tests/test_cumulative_balance_domain.py`

**Interfaces:**
- Consumes: `_actual_minutes(work_date, entries, settings) -> int | None`, `month_workdays` from `build_forecast()`.
- Produces: `DayForecast.daily_balance_minutes: int | None` and `DayForecast.cumulative_balance_minutes: int | None`.

- [ ] **Step 1: Write failing domain tests**

Test daily values `+10`, `-40`, `0`, running values `+10`, `-30`, `-30`, missing values `None`, weekly carry-in from prior month days, and August reset.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `poetry run python -B -m pytest tests/test_cumulative_balance_domain.py -v -p no:cacheprovider`

Expected: collection or assertion failure because the balance fields do not exist.

- [ ] **Step 3: Implement the month ledger**

Add the two optional minute fields to `DayForecast`. Add a helper that iterates `month_workdays`, calculates `daily = actual - settings.target_minutes_per_day`, updates a signed running total, and returns values only for complete records. Populate every `DayForecast` branch without changing target forecasting.

- [ ] **Step 4: Verify domain tests**

Run the focused tests plus `tests/test_domain.py` and `tests/test_month_ledger.py`; expect all to pass.

### Task 2: Web Table Presentation

**Files:**
- Modify: `src/workhours/templates/index.html`
- Modify: `src/workhours/static/styles.css`
- Create: `tests/test_cumulative_balance_web.py`

**Interfaces:**
- Consumes: `DayForecast.daily_balance_minutes` and `DayForecast.cumulative_balance_minutes`; existing `signed_minutes` filter.
- Produces: a “累计余额” cell with signed cumulative and daily values plus semantic positive/negative/neutral classes.

- [ ] **Step 1: Write failing Web tests**

Create records whose effective times are 9h10m, 8h20m, 9h, and 9h30m. Assert the week page has no “建议下班” header, has the “累计余额” header, exposes exact minute data attributes, and renders a missing row with no balance.

- [ ] **Step 2: Run Web tests and verify RED**

Run: `poetry run python -B -m pytest tests/test_cumulative_balance_web.py -v -p no:cacheprovider`

Expected: failure because the new header and cells are absent.

- [ ] **Step 3: Replace the column and add styles**

Remove only the suggested-end header/cell from the table. Render cumulative balance as the main signed value, daily balance beneath it, and `-` for `None`. Add green, red, and neutral classes with stable cell dimensions and mobile-safe wrapping.

- [ ] **Step 4: Verify Web tests**

Run the focused Web test plus existing Web tests; expect all to pass.

### Task 3: Final Verification and Service Restart

**Files:**
- Modify: `README.md` only if the visible feature summary requires an update.

**Interfaces:**
- Consumes: completed domain and Web behavior.
- Produces: a verified background service on an available localhost port.

- [ ] **Step 1: Run all automated checks**

Run `poetry run python -B -m pytest -q -p no:cacheprovider` and `poetry check`; expect success.

- [ ] **Step 2: Verify the rendered UI**

Use Playwright at desktop and 390px mobile widths. Confirm the replacement column is visible, signed colors are correct, the table remains horizontally contained, and the console has no errors.

- [ ] **Step 3: Restart the latest background service**

Stop only the process started by this task, restart the app hidden on the selected port with the formal `workhours.sqlite3`, request the page, and require HTTP 200.
