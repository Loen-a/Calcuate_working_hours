import type { DayInfo, HolidayMap } from './types'
import { pad } from './workHours'

export function dayInfo(y: number, m: number, d: number, hMap?: HolidayMap): DayInfo {
  const wd = new Date(y, m - 1, d).getDay() // 0=周日 .. 6=周六
  const weekend = wd === 0 || wd === 6
  const h = (hMap || {})[`${pad(m)}-${pad(d)}`]
  if (h) return { type: h.isOffDay ? 'rest' : 'work', name: h.name, isOffDay: h.isOffDay, weekend }
  return { type: weekend ? 'rest' : 'work', weekend }
}

export function workingDaysInMonth(y: number, m: number, hMap?: HolidayMap): number {
  const days = new Date(y, m, 0).getDate()
  let n = 0
  for (let d = 1; d <= days; d++) if (dayInfo(y, m, d, hMap).type === 'work') n++
  return n
}
