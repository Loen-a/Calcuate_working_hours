// Presentation only: minutes and attendance decisions are supplied by Flask.
export function fmtMinutes(value: number): string {
  const total = Math.round(Math.abs(value))
  const hours = Math.floor(total / 60)
  const minutes = total % 60
  const label = hours ? `${hours}h${minutes ? ` ${String(minutes).padStart(2, '0')}m` : ''}` : `${minutes}m`
  return `${value < 0 ? '−' : ''}${label}`
}
export const signedMinutes = (value: number) => `${value > 0 ? '+' : ''}${fmtMinutes(value)}`
export const fmtDate = (y: number, m: number, d: number) =>
  `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
export function calendarDate(year: number, monthIndex: number, day: number): Date {
  const value = new Date(0)
  value.setHours(12, 0, 0, 0)
  // The multi-argument Date constructor changes years 0–99 to 1900–1999.
  value.setFullYear(year, monthIndex, day)
  return value
}
export function shiftMonth(date: string, delta: number): string {
  const [y, m, d] = date.split('-').map(Number)
  const next = calendarDate(y, m - 1 + delta, 1)
  const last = calendarDate(next.getFullYear(), next.getMonth() + 1, 0).getDate()
  return fmtDate(next.getFullYear(), next.getMonth() + 1, Math.min(d, last))
}
