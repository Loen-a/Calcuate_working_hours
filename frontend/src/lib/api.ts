import type { CalendarKind, DashboardData, Entry, Interval, Period, Preview, Theme } from './types'

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json() as { error?: unknown }
      if (typeof body.error === 'string') message = body.error
    } catch { /* Preserve a useful error when the response is not JSON. */ }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
const json = (method: string, body: unknown): RequestInit => ({
  method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
})
export const getDashboard = (date = '') => request<DashboardData>(
  '/api/dashboard' + (date ? '?reference_date=' + encodeURIComponent(date) : ''),
)
export const putEntry = (date: string, entry: Entry) =>
  request<void>('/api/entries/' + encodeURIComponent(date), json('PUT', entry))
export const deleteEntry = (date: string) =>
  request<void>('/api/entries/' + encodeURIComponent(date), { method: 'DELETE' })
export const setLeave = (date: string, enabled: boolean) =>
  request<void>('/api/leaves/' + encodeURIComponent(date), json('PUT', { enabled }))
export const putSettings = (settings: { period?: Period; theme?: Theme }) =>
  request<void>('/api/settings', json('PUT', settings))
export const setCalendar = (date: string, kind: CalendarKind | null) => request<void>(
  '/api/calendar/' + encodeURIComponent(date), kind ? json('PUT', { kind }) : { method: 'DELETE' },
)
export const saveInterval = (interval: Omit<Interval, 'interval_id'> & { interval_id?: number }) =>
  request<void>('/api/non-working-intervals', json('POST', interval))
export const deleteInterval = (id: number) =>
  request<void>('/api/non-working-intervals/' + id, { method: 'DELETE' })
export const refreshHolidays = (year: number) =>
  request<DashboardData['holiday_status']>('/api/holidays/' + year + '/refresh', { method: 'POST' })
export const getPreview = (date: string, start: string, signal?: AbortSignal) =>
  request<Preview>('/preview/earliest-end?' + new URLSearchParams({ work_date: date, start_time: start }), { signal })
export const clock = (kind: 'in' | 'out') => request<{ date: string }>('/api/clock-' + kind, { method: 'POST' })
export function downloadBackup(): void {
  const anchor = document.createElement('a')
  anchor.href = '/api/backup'
  anchor.download = ''
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}
export function importBackup(file: File): Promise<{ version: number; entries: number }> {
  const body = new FormData()
  body.append('file', file)
  return request('/api/backup', { method: 'POST', body })
}
