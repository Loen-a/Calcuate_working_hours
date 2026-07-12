import type { DayInfo, HolidayMap } from './types'
import { loadHolidayCache, saveHolidayCache } from './storage'
import { pad } from './workHours'

const holidayMem: Record<number, HolidayMap> = {}

// 节假日数据来源: NateScarlet/holiday-cn (含调休)，经双 CDN 拉取，按年缓存到本地
export async function fetchHolidays(year: number): Promise<HolidayMap> {
  if (holidayMem[year]) return holidayMem[year]
  const cached = loadHolidayCache(year) as HolidayMap | null
  if (cached) {
    holidayMem[year] = cached
    return cached
  }
  const urls = [
    `https://cdn.jsdelivr.net/gh/NateScarlet/holiday-cn@master/${year}.json`,
    `https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/${year}.json`,
  ]
  let json: { days?: Array<{ name: string; date: string; isOffDay: boolean }> } | null = null
  for (const u of urls) {
    try {
      const r = await fetch(u)
      if (r.ok) {
        json = await r.json()
        break
      }
    } catch {
      /* try next */
    }
  }
  const map: HolidayMap = {}
  if (json && Array.isArray(json.days)) {
    for (const d of json.days) {
      const p = String(d.date).split('-')
      if (p.length === 3) map[`${p[1]}-${p[2]}`] = { name: d.name, isOffDay: !!d.isOffDay }
    }
  }
  holidayMem[year] = map
  saveHolidayCache(year, map)
  return map
}

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
