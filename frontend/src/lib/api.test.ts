import { afterEach, expect, it, vi } from 'vitest'
import { ApiError, getDashboard, importBackup, putEntry, setLeave } from './api'

afterEach(() => vi.unstubAllGlobals())
it('keeps all dashboard and mutation requests on the Flask origin', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{}', { headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)
  await getDashboard('2026-09-08')
  expect(fetch).toHaveBeenCalledWith('/api/dashboard?reference_date=2026-09-08', undefined)
  fetch.mockResolvedValue(new Response(null, { status: 204 }))
  await putEntry('2026-09-08', { start_time: '22:00', end_time: null })
  expect(fetch).toHaveBeenLastCalledWith('/api/entries/2026-09-08', expect.objectContaining({ method: 'PUT', body: '{"start_time":"22:00","end_time":null}' }))
  await setLeave('2026-09-08', true)
  expect(fetch).toHaveBeenLastCalledWith('/api/leaves/2026-09-08', expect.objectContaining({ method: 'PUT', body: '{"enabled":true}' }))
})
it('surfaces the server error and uploads backups as the required multipart file field', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{"error":"不兼容的计入设置"}', { status: 400 }))
  vi.stubGlobal('fetch', fetch)
  const file = new File(['{}'], 'backup.json', { type: 'application/json' })
  await expect(importBackup(file)).rejects.toMatchObject({ name: 'ApiError', status: 400, message: '不兼容的计入设置' })
  const body = fetch.mock.calls[0][1].body as FormData
  expect(body.get('file')).toBe(file)
})
it('gives a useful error for an HTML error response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>offline</html>', { status: 503 })))
  await expect(getDashboard()).rejects.toEqual(new ApiError(503, '请求失败（503）'))
})
