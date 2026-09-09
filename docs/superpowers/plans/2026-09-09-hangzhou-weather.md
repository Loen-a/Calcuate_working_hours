# Hangzhou calendar weather

**Scope:** The user selected Hangzhou for the proposed PC calendar weather feature. Keep working on `feat/desktop-workspace`; do not merge into main. Show a small weather icon and low/high Celsius temperatures for the seven-day forecast including today. Past dates and dates outside the forecast are blank. Existing punches, holiday/leave labels, mobile layout and business calculations remain unchanged.

**Location:** Zhejiang Hangzhou, Open-Meteo geocoding ID 1808926, latitude 30.29365, longitude 120.16142, timezone Asia/Shanghai. Fixed configuration for this first version; no geolocation, city selector or new API key UI.

**Architecture:** A separate GET `/api/weather?month=YYYY-MM` serves weather independently of `/api/dashboard`. The frontend loads it only on PC after the dashboard and on viewed-month changes, refreshes hourly and at Hangzhou midnight while active, and cancels obsolete requests. Visibility return checks both age and Hangzhou local date. Weather loading/failure must not set the existing application mutation/loading lock. Backend fetches seven days in one HTTPS request and caches them for one hour. Midnight invalidates the forecast window. Failed refresh can return only still-relevant cached forecast dates, marked stale; never manufacture history or weather values.

## Contracts

`get_weather(store, month: date, now: datetime | None = None, allow_network=True, fetcher=None)` returns an immutable WeatherResult with `city`, `timezone`, `month` (YYYY-MM), `forecast_start`, `forecast_end`, `source` (remote/cache/unavailable), `stale`, `fetched_at` (UTC ISO string or null), `warning` (string or null), and `days` (date-keyed dictionary).

Each day contains `code` (integer), `description` (Chinese), `icon` (clear/partly-cloudy/cloudy/fog/drizzle/rain/snow/thunderstorm), `temperature_min` and `temperature_max` (finite Celsius numbers). Both source payload dates and output dates must match Hangzhou local calendar dates. Skip dates with null observations instead of inventing defaults; reject malformed non-null numbers, unexpected codes, duplicate dates and inconsistent array lengths before replacing cache.

Storage adds only `weather_cache(location_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, fetched_at TEXT NOT NULL)`. `WorkHoursStore.get_weather_cache(location_key)` returns `(payload_dict, timestamp)` or None; `set_weather_cache(location_key,payload,fetched_at)` writes it. Payload records `forecast_date` and normalized `days`. Weather cache is rebuildable external data and is excluded from work-hour backups; city is fixed in the weather service, not new user data.

App configuration: `WEATHER_NETWORK_ENABLED` defaults true, `WEATHER_FETCHER` optional callable URL -> decoded JSON, `WEATHER_NOW_PROVIDER` optional aware datetime callable for deterministic tests. Production time derives from UTC+08:00 independently of server timezone.

## Tasks

- [x] Weather service/store worker: implement fixed-city request, daily validation and Chinese/icon mapping, hour/midnight cache expiry and safe stale fallback; write and run meaningful red/green tests.
- [x] Frontend worker: add typed weather client and independent hook, integrate PC calendar weather/attribution, preserve cell/punch/holiday layout and mobile behavior; test delayed/failed weather and obsolete responses. Do not build before baseline capture finishes.
- [x] Root: expose isolated API, test valid/invalid month and dashboard independence, document behavior and validate live provider data with a temporary DB.
- [x] Acceptance: run Python/frontend tests and production build; verify real PC weather, all themes, narrow desktop fit, mobile unchanged, offline/stale states, seven-day range and date selection/editing while weather is delayed. Commit locally on feature branch only.


## Verification evidence

- Backend: `poetry run pytest -q` — 224 passed, including 48 weather service/API cases. No work-hour domain or backup contract changes.
- Frontend: Node 22 full suite — 60 passed; after the final CSS-token fix, Calendar's 22 tests and the TypeScript/Vite production build passed again.
- Real Chrome: 12 desktop combinations (cool/teal/classic at 1024/1280/1440/1920), no overflow, holiday/leave labels retained. Wide cells show temperatures; narrower cells show the icon and full hover details.
- Real Flask and Chrome: date selection via weather, same-month no refetch, month switching, saving punches while weather is delayed, unavailable weather with working editor, stale cache excluding yesterday, and PC/mobile resizing all passed with no browser errors.
- Mobile: 27 before/after visible-text, font, colour and geometry snapshots matched exactly (390/768/1023 widths; three themes; page/editor/time picker). Fixed the Tailwind scanner regression before acceptance; the emitted `.truncate` rule matches the previous build.
- Live Open-Meteo via a temporary database: Hangzhou `Asia/Shanghai`, source `remote`, seven dates 2026-09-09 through 2026-09-15, fetched at 2026-09-09T02:27:14Z. Earlier direct service check also confirmed the next request used the identical cached data.
- Browser fixtures, results and 2x screenshots are kept under ignored `output/acceptance/weather/`; no test database or test-only control route enters production. Feature branch only; remote publication is separate.
