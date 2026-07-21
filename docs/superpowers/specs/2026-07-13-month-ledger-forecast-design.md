# Month-Ledger Forecast Design

## Goal

Make the natural calendar month the authoritative work-hour ledger. Weekly mode remains available as a short planning horizon, but it must carry the signed balance from earlier workdays in the same month instead of starting from zero every Monday.

## Confirmed Business Rules

- The target for each adjusted workday is 9 effective hours.
- A normal workday must still receive a recommendation of at least 8 effective hours, even when the target is already met.
- The default lunch break is 90 minutes and is never counted as effective work time.
- Holidays and adjusted workdays come from the user's calendar overrides.
- Natural months are independent. Surplus or deficit does not cross a month boundary.
- A week that crosses a month boundary is clipped to the selected date's month. Dates in the other month are calculated from that month's ledger when that month is selected.

## Forecast Modes

### Monthly Mode

The planning target is every adjusted workday in the selected natural month multiplied by 9 hours. Recorded effective time and earlier monthly balance are shared across the whole month. The remaining target is distributed across unrecorded workdays from the selected date through month end, subject to the 8-hour daily minimum.

### Weekly Mode

The visible and recommended dates are the selected week intersected with the selected natural month. Earlier adjusted workdays in the same month contribute a signed carry balance:

`carry balance = earlier target - earlier accounted time`

Positive values are deficits and increase the current week's target. Negative values are surpluses and reduce it. The adjusted target is distributed across the current week's remaining workdays, subject to the 8-hour daily minimum.

The first week segment of a month has no earlier monthly carry balance.

## Missing Historical Records

A past adjusted workday without both clock-in and clock-out times is unknown, not zero. For planning only, it receives a neutral 9-hour credit so it contributes neither surplus nor deficit. The dashboard lists the missing dates and states that the forecast is provisional. Saving the real entry replaces the neutral credit and recalculates immediately.

Past missing days do not receive future recommendations. Recommendations are only generated for unrecorded workdays on or after the selected reference date.

## Domain Changes

`build_forecast` will always derive a full month ledger, then select the planning horizon for the chosen mode. `Forecast` will expose:

- the selected display period;
- the mode target and completed time;
- the full monthly target and recorded time;
- the signed carry balance for weekly mode;
- missing historical dates;
- daily actuals, recommendations, reasons, and suggested clock-out times.

SQLite schema changes are not required.

## Web And UI Changes

The dashboard will load entries and calendar overrides for the entire selected month even in weekly mode. The weekly table remains limited to the clipped week segment.

The summary will emphasize monthly target and recorded progress. Weekly mode will additionally show its base target, monthly carry balance, and adjusted remaining target. A warning appears when historical records are missing and explains the neutral 9-hour assumption.

## Verification

Automated tests will cover monthly deficit distribution, weekly deficit and surplus carry, first-week reset, cross-month clipping, adjusted holidays/workdays, missing-history neutral credit, and the expanded Web query/rendering behavior. Existing minimum-day and lunch-break behavior must continue to pass.
