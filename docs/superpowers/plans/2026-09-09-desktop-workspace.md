# Desktop workspace redesign

**Goal:** On a new branch, use PC screen width effectively and make the work-hour app clearer and brighter with the existing business features.

**Approved design:** PC content width `min(1600px, 100% - 64px)`; at 1280px and above, calendar plus a 340px selected-day panel separated by 24px; 1024–1279px stacks these areas; below 1024px retains the current mobile view. A compact monthly summary precedes the calendar. Trends and settings follow it. Calendar rows adapt to the displayed month on PC. Main surfaces are white, backgrounds nearly white, and each existing theme keeps its accent color. Prediction text is 40–48px, monthly statistics 24px. No backend, data, or business-rule changes.

**Architecture:** Continue using `DashboardData`, shared Flask APIs and the existing `EntryModal`. On PC, clicking a calendar date selects it and refreshes the side panel; its explicit edit action opens the existing modal. Mobile keeps click-to-edit. Desktop visual changes stay within media queries in `frontend/src/desktop.css`.

**Color/type:** Near-white backgrounds (#f7f9fc cool, #f6faf8 teal, #f5f7f4 classic), white cards (#ffffff), existing theme text/positive/negative colors. Keep the approved Segoe UI / Microsoft YaHei desktop stack. Give the date grid visual priority instead of a full-width dark prediction hero. Use concise Chinese labels on PC and preserve mobile content.

```text
Title + month navigation                 Backup / theme / old view
Date selection                          Current clock-in / clock-out
Monthly target | Recorded | Balance | Workdays
Calendar (flexible width)                Selected date (340px)
                                        Punches / prediction / edit
Trend chart
Expandable settings and holiday refresh
```

## File ownership and interfaces

- Root: `App.tsx`, `App.test.tsx`, `Dashboard.tsx`, `desktop.css`, README and acceptance artifacts. Wire responsive layout and existing actions; keep desktop and mobile content mutually exclusive.
- Calendar/Header worker: `Calendar.tsx`, `Calendar.test.tsx`, `Header.tsx`. Add optional `desktop?: boolean` to Calendar, default false for old callers. On PC compute rows from first-week offset + month length (4/5/6 rows); accessible name `选择 YYYY-MM-DD`, `aria-pressed` identifies selected date. Mobile stays 42 cells and `编辑 YYYY-MM-DD`. Keep `onPick` returning the date only. Header preserves props; add named classes for container, brand, month nav and utility actions so root can consolidate the desktop toolbar via CSS.
- Selected-day worker: new `SelectedDayPanel.tsx` and its tests. Props `{day: Day, preview: Preview, today: string, busy: boolean, onEdit: () => void}`. Show backend dates/punches/actual minutes, leave/rest/missing state, balance-before and required work, and suggested-end label (including next-day offset). `onEdit` opens existing modal; no direct mutations or new calculations. Use semantic classes for root desktop CSS; no fixed dark background. Guard missing start / unavailable prediction with clear text.

## Steps

- [x] Create the branch and verify the existing frontend baseline.
- [x] Capture unchanged mobile/browser baseline with a temporary database before replacing the build.
- [x] Add meaningful regression tests for PC date selection vs mobile editing, calendar row count and selected-day status; run red then implement.
- [x] Integrate layout, selected-day panel, brighter theme surfaces and compact summary; keep all existing controls reachable.
- [x] Run frontend tests and production build. Validate at 1024, 1280, 1440 and 1920px; verify mobile typography/layout and theme fallback, edit/leave/backup actions, and no page or modal overflow.
- [x] Review the diff, update usage notes, and commit on the new branch. Do not merge into main.

## Verified result

- Branch: `feat/desktop-workspace`, based on main commit `0a2bdb5`; main remains unchanged.
- Frontend baseline: 26 passing tests; after implementation and keyboard-focus correction: 47 passing tests. TypeScript and production Vite build passed.
- PC browser checks: 1024, 1280, 1440 and 1920 CSS pixels across all three themes (12 cases); content width, column/stack placement, month row counts, actual cell height below 108px and page/modal overflow checked.
- Mobile visual regression: 390, 768 and 1023px, three themes, page/modal/time picker (27 cases); text typography and layout metrics matched the pre-change snapshots.
- Real browser actions against a temporary SQLite database: PC selection without writes, keyboard focus after successful/failed loading, explicit edit, start-only save, failed-save draft retention, rest/leave/overnight details, leave cancellation, period and interval settings, backup download/import, interface switching, 4/5/6-week calendar shapes and mobile click-to-edit all passed without page errors.
- Visual review: 1440 and 1920px screenshots independently reviewed; no clipped controls or missing approved actions found.
- Evidence and 2x previews: ignored `output/acceptance/workspace/`. Browser comparisons block external font downloads for consistent rendering; system fallback fonts vary by host. No live work-hour database was used.
