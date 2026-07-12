import type { Entries } from './types'

const DATA_KEY = 'workhours_v1'
const HOLIDAY_CACHE = 'holidaycn_v1_'

export function loadEntries(): Entries {
  try {
    return JSON.parse(localStorage.getItem(DATA_KEY) || '{}')
  } catch {
    return {}
  }
}

export function saveEntries(e: Entries): void {
  localStorage.setItem(DATA_KEY, JSON.stringify(e))
}

export function loadHolidayCache(year: number): unknown {
  try {
    return JSON.parse(localStorage.getItem(HOLIDAY_CACHE + year) || 'null')
  } catch {
    return null
  }
}

export function saveHolidayCache(year: number, map: unknown): void {
  try {
    localStorage.setItem(HOLIDAY_CACHE + year, JSON.stringify(map))
  } catch {
    /* ignore */
  }
}
