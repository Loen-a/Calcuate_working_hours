export const DAILY_TARGET = 9 // 每日目标工时(小时)
export const LUNCH: [number, number] = [12 * 60, 13.5 * 60] // 午休 12:00-13:30
export const DINNER: [number, number] = [19.5 * 60, 20 * 60] // 晚休 19:30-20:00

export const pad = (n: number) => String(n).padStart(2, '0')
export const fmtDate = (y: number, m: number, d: number) => `${y}-${pad(m)}-${pad(d)}`

export function parseTime(s: string | null | undefined): number | null {
  if (!s) return null
  const [h, m] = s.split(':').map(Number)
  if (isNaN(h) || isNaN(m)) return null
  return h * 60 + m
}

export function overlap(aS: number, aE: number, bS: number, bE: number): number {
  return Math.max(0, Math.min(aE, bE) - Math.max(aS, bS))
}

// 净工时(小时)；下班≤上班(含跨天)返回 null
export function calcNet(inStr: string, outStr: string): number | null {
  const i = parseTime(inStr)
  const o = parseTime(outStr)
  if (i == null || o == null) return null
  if (o <= i) return null
  const gross = o - i
  const ded = overlap(i, o, LUNCH[0], LUNCH[1]) + overlap(i, o, DINNER[0], DINNER[1])
  return (gross - ded) / 60
}

// 小数小时 → "X小时Y分钟"（分钟为 0 省掉，小时为 0 只留"X分钟"）
export function fmtDuration(h: number): string {
  const abs = Math.abs(h)
  if (abs === 0) return '0分钟'
  let hh = Math.floor(abs)
  let mm = Math.round((abs - hh) * 60)
  if (mm === 60) {
    hh += 1
    mm = 0
  }
  if (mm === 0) return `${hh}小时`
  if (hh === 0) return `${mm}分钟`
  return `${hh}小时${mm}分钟`
}

// 该条记录是否计入工时：workday 默认计入；rest day 默认不计入（除非显式 counts=true）
export function isEntryCounted(counts: boolean | undefined, isWorkday: boolean): boolean {
  if (counts === true) return true
  if (counts === false) return false
  return isWorkday
}

// 补时长按半小时向下取整：2h02m→2h、3h39m→3h30m、2h29m→2h
export function floorTo30Min(h: number): number {
  const totalMin = Math.round(h * 60)
  return Math.floor(totalMin / 30) * 30 / 60
}
