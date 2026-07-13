import type {
  Entries,
  HolidayMap,
  HolidaySource,
  Theme,
  WorkEntry,
} from './types'

const API_ROOT = import.meta.env.DEV
  ? 'http://127.0.0.1:8000/api'
  : '/api'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API_ROOT + path, init)
  if (!response.ok) {
    let message = '请求失败'
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // Keep the stable fallback for non-JSON errors.
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const getEntries = () => request<Entries>('/entries')

export async function putEntry(
  date: string,
  entry: WorkEntry,
): Promise<WorkEntry> {
  const result = await request<{ date: string; entry: WorkEntry }>(
    '/entries/' + encodeURIComponent(date),
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entry),
    },
  )
  return result.entry
}

export const deleteEntry = (date: string) =>
  request<void>('/entries/' + encodeURIComponent(date), { method: 'DELETE' })

export const getPreferences = () =>
  request<{ theme: Theme }>('/preferences')

export const putPreferences = (theme: Theme) =>
  request<{ theme: Theme }>('/preferences', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme }),
  })

export interface HolidayApiResponse {
  year: number
  holidays: HolidayMap
  source: HolidaySource
}

export const getHolidays = (year: number) =>
  request<HolidayApiResponse>('/holidays/' + year)

export function downloadBackup(): void {
  const anchor = document.createElement('a')
  anchor.href = API_ROOT + '/backup'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

export function importBackup(file: File): Promise<{
  version: number
  entries: number
  holidayYears: number
}> {
  const body = new FormData()
  body.append('file', file)
  return request('/backup', { method: 'POST', body })
}
