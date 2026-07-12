import { useMemo } from 'react'
import type { Entries, HolidayMap } from './types'
import { dayInfo, workingDaysInMonth } from './holidays'
import { calcNet, DAILY_TARGET, fmtDate, floorTo30Min, isEntryCounted } from './workHours'

export interface MonthStats {
  wd: number
  target: number
  done: number
  entered: number
  balance: number
}

export function useMonthStats(
  y: number,
  m: number,
  entries: Entries,
  hMap?: HolidayMap,
): MonthStats {
  return useMemo(() => {
    const wd = workingDaysInMonth(y, m, hMap)
    const target = DAILY_TARGET * wd
    let done = 0
    let entered = 0
    let workdayEntered = 0
    const days = new Date(y, m, 0).getDate()
    for (let d = 1; d <= days; d++) {
      const info = dayInfo(y, m, d, hMap)
      const e = entries[fmtDate(y, m, d)]
      if (e && isEntryCounted(e.counts, info.type === 'work')) {
        const net = calcNet(e.in, e.out)
        if (net != null) {
          const isWorkday = info.type === 'work'
          done += isWorkday ? net : floorTo30Min(net)
          entered++
          if (isWorkday) workdayEntered++
        }
      }
    }
    const balance = done - DAILY_TARGET * workdayEntered
    return { wd, target, done, entered, balance }
  }, [y, m, entries, hMap])
}
