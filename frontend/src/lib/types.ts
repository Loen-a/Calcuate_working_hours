export interface WorkEntry {
  in: string   // "HH:MM"
  out: string  // "HH:MM"
  counts?: boolean // true=计入工时；rest day 默认 false，workday 默认 true
}
export type Entries = Record<string, WorkEntry> // "YYYY-MM-DD" -> entry

export type Theme = 'cool' | 'teal'
export type HolidaySource = 'cache' | 'remote' | 'fallback'

export interface HolidayInfo {
  name: string
  isOffDay: boolean
}
export type HolidayMap = Record<string, HolidayInfo> // "MM-DD" -> info

export interface DayInfo {
  type: 'work' | 'rest'
  name?: string
  isOffDay?: boolean
  weekend: boolean
}
