# Configurable Non-Working Intervals Design

## Goal

Replace the fixed 90-minute deduction with configurable recurring time intervals that do not count as effective work. The monthly ledger, weekly carry, daily recommendations, and suggested clock-out time must all use the same interval rules.

## Confirmed Rules

- Seed two enabled defaults on first initialization only:
  - `Lunch`: 12:00-13:30.
  - `Evening break`: 19:30-20:00.
- Time after 20:00 counts as work again.
- Rules recur on every workday and are global rather than date-specific.
- Users can add, edit, enable, disable, and delete rules.
- A rule requires a non-empty name and a start time earlier than its end time.
- Overlapping enabled rules are merged before deduction so the same minute is never subtracted twice.
- Historical entries are recalculated with the current enabled rules whenever the dashboard is loaded.

## Effective-Time Calculation

Effective time is the attendance duration minus the union of all enabled rule intervals that overlap the attendance window. A rule only subtracts the minutes that actually overlap the entry.

Examples with the defaults:

- 09:00-20:30 counts 9 hours 30 minutes: 11 hours 30 minutes attendance minus 1 hour 30 minutes lunch and 30 minutes evening break.
- 13:30-19:45 counts 6 hours: only 19:30-19:45 overlaps a non-working interval.
- 20:00-21:00 counts 1 hour.

Overnight attendance remains supported. Recurring intervals apply independently to each calendar day covered by the entry.

## Suggested Clock-Out Time

Suggested clock-out calculation advances along the timeline and skips every enabled non-working interval. For example, a 10-hour recommendation starting at 09:00 ends at 21:00 because 12:00-13:30 and 19:30-20:00 are skipped.

## Domain Model

Add an immutable `NonWorkingInterval` value object containing an optional database id, name, start time, end time, and enabled flag. `ForecastSettings` carries the active interval collection. All actual-time and suggested-end calculations consume this collection.

The legacy `entries.lunch_minutes` column and `WorkEntry.lunch_minutes` field remain for database compatibility, but interval rules become authoritative for forecast calculations.

## Persistence

Add a SQLite `non_working_intervals` table with integer id, name, start time, end time, and enabled flag. A settings marker records that defaults have been seeded, so intentionally deleting every rule does not recreate defaults on restart.

Storage exposes list, upsert, and delete operations. Existing databases upgrade through `CREATE TABLE IF NOT EXISTS` without changing entry rows.

## Web UI

Add a full-width `Non-working time` section containing:

- an add form with name, start, end, and enabled controls;
- an editable row for every existing rule;
- save and delete actions;
- concise validation feedback for empty names and invalid ranges.

The header reports the number of enabled rules instead of the fixed 90-minute lunch text. Saving any rule redirects back to the currently selected date and immediately recalculates the dashboard.

## Testing

Tests cover overlap-only deductions, overlapping-rule merging, time after 20:00, suggested-end skipping, overnight entries, default seeding, CRUD and persistence, rule validation, historical recalculation, and unchanged monthly/weekly ledger behavior.
