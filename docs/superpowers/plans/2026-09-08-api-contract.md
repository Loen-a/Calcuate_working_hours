# Shared Flask API

All frontend calls use same-origin `/api`; errors return `{error: string}` and non-2xx. After successful mutations, reload the selected dashboard. Dates are YYYY-MM-DD; times HH:MM or null; values called minutes are integer minutes, never recompute business rules in JS.

## Dashboard

`GET /api/dashboard?reference_date=2026-09-08`

```typescript
interface Entry { start_time: string | null; end_time: string | null }
interface Interval { interval_id: number; name: string; start_time: string; end_time: string; enabled: boolean }
interface Day {
  date: string; is_workday: boolean; leave: boolean;
  calendar_name: string; manual_override: 'holiday' | 'workday' | null;
  entry: Entry | null; actual_minutes: number | null;
  daily_balance_minutes: number | null; cumulative_balance_minutes: number | null;
  balance_before_minutes: number; required_minutes: number | null;
  recommended_minutes: number | null; suggested_end: string | null;
  suggested_end_day_offset: number | null; reason: string; compliant: boolean | null;
}
interface Preview {
  available: boolean; required_minutes?: number; required_label?: string;
  balance_before_minutes?: number; balance_label?: string; reason_label?: string;
  suggested_end?: string | null; suggested_end_label?: string; day_offset?: number | null;
}
interface Dashboard {
  today: string; selected_date: string; theme: 'cool' | 'teal';
  settings: {period: 'week' | 'month'; target_minutes_per_day: number; minimum_minutes_per_day: number};
  intervals: Interval[]; days: Day[]; selected_preview: Preview;
  month: {start: string; end: string; target_minutes: number; completed_minutes: number;
    balance_minutes: number; remaining_target_minutes: number; workday_count: number;
    recorded_days: number; missing_history_days: string[]};
  forecast: {period_start: string; period_end: string; target_minutes: number;
    completed_minutes: number; remaining_target_minutes: number; carryover_minutes: number; goal_met: boolean};
  holiday_status: {year: number; source: 'cache' | 'remote' | 'fallback'; warning: string | null};
}
```

`days` includes every calendar date in the selected month, using a monthly forecast and selected_date as the reference. `forecast` supplies selected week/month aggregate. Leave dates have no counted actual minutes or prediction; preserved punches are still present in entry. Calendar_name explicitly identifies leave/rest/holiday/manual workday.

## Mutations and preview

- `PUT /api/entries/<date>` JSON `{start_time: string|null, end_time: string|null}`; incomplete and overnight records accepted. Does not change leave or manual overrides.
- `DELETE /api/entries/<date>` removes punches only.
- `POST /api/clock-in`, `POST /api/clock-out` record server local current date/time. Response `{date: YYYY-MM-DD}`.
- `PUT /api/leaves/<date>` JSON `{enabled: boolean}`.
- `PUT /api/settings` JSON `{period?: 'week'|'month', theme?: 'cool'|'teal'}`.
- `PUT /api/calendar/<date>` JSON `{kind: 'holiday'|'workday'}`; `DELETE` removes manual override only.
- `POST /api/non-working-intervals` JSON `{interval_id?: number, name: string, start_time: string, end_time: string, enabled: boolean}`.
- `DELETE /api/non-working-intervals/<id>`.
- `POST /api/holidays/<year>/refresh` returns `{year,source,warning}`; stale cache is retained when upstream fails.
- `GET /preview/earliest-end?work_date=<date>&start_time=<HH:MM>` returns Preview; calendar and leave handled by Python.
- `GET /api/backup` downloads JSON attachment. `POST /api/backup` multipart field `file`, only after user explicitly confirms replacement; returns summary. On success refresh the dashboard; on failure show error without claiming success.
- `GET /interface/old?reference_date=<date>` and `/interface/new?...` set the browser preference cookie and redirect to `/` with selected date. `/` defaults new. `/?ui=old` explicitly renders legacy; `/?ui=new` explicitly renders React.

New interface must expose main's period, manual calendar and editable non-working interval settings, selected-date punches and earliest-end preview, leave checkbox/cancel, backup and refresh. Preserve local-main visual design, themes and charts; remove counts and any independent net-work/forecast formulas. Use backend numeric results for cards and plots. Keep import/leave actions available in both views. Theme choice is separate from new/old interface choice.
