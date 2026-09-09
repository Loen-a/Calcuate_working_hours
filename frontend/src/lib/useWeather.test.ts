import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { getWeather } from './api'
import { useWeather } from './useWeather'
import type { WeatherResult } from './types'

vi.mock('./api', () => ({ getWeather: vi.fn() }))
const resultFor = (month: string): WeatherResult => ({
  city: '杭州', timezone: 'Asia/Shanghai', month, forecast_start: '2026-09-09', forecast_end: '2026-09-15',
  source: 'cache', stale: false, fetched_at: '2026-09-09T01:00:00Z', warning: null,
  days: month === '2026-09' ? { '2026-09-09': { code: 61, description: '小雨', icon: 'rain', temperature_min: 23.4, temperature_max: 29.1 } } : {},
})
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(finish => { resolve = finish })
  return { promise, resolve }
}
beforeEach(() => {
  vi.mocked(getWeather).mockReset().mockImplementation(async month => resultFor(month))
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
})
afterEach(() => vi.useRealTimers())

it('cancels an obsolete month and ignores its late response even if transport ignores abort', async () => {
  const old = deferred<WeatherResult>()
  const current = deferred<WeatherResult>()
  vi.mocked(getWeather).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
  const { result, rerender } = renderHook(({ month }) => useWeather(month, true), { initialProps: { month: '2026-09' } })
  const oldSignal = vi.mocked(getWeather).mock.calls[0][1]!
  rerender({ month: '2026-10' })
  expect(oldSignal.aborted).toBe(true)
  expect(result.current.data).toBeNull()
  await act(async () => current.resolve(resultFor('2026-10')))
  expect(result.current.data?.month).toBe('2026-10')
  await act(async () => old.resolve(resultFor('2026-09')))
  expect(result.current.data?.month).toBe('2026-10')
  expect(result.current.data?.days['2026-09-09']).toBeUndefined()
})

it('does not request on mobile and refreshes when returning to PC without refetching the same month on rerender', async () => {
  const { result, rerender } = renderHook(({ enabled }) => useWeather('2026-09', enabled), { initialProps: { enabled: false } })
  expect(getWeather).not.toHaveBeenCalled()
  rerender({ enabled: true })
  await waitFor(() => expect(result.current.data?.month).toBe('2026-09'))
  rerender({ enabled: true })
  expect(getWeather).toHaveBeenCalledTimes(1)
  const firstSignal = vi.mocked(getWeather).mock.calls[0][1]!
  rerender({ enabled: false })
  expect(firstSignal.aborted).toBe(true)
  expect(result.current.data).toBeNull()
  rerender({ enabled: true })
  await waitFor(() => expect(getWeather).toHaveBeenCalledTimes(2))
})

it('refreshes hourly when visible, skips hidden polls, and retries when active again', async () => {
  vi.useFakeTimers()
  const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  renderHook(() => useWeather('2026-09', true))
  await act(async () => undefined)
  expect(getWeather).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(60 * 60 * 1000) })
  expect(getWeather).toHaveBeenCalledTimes(2)
  visibility.mockReturnValue('hidden')
  await act(async () => { await vi.advanceTimersByTimeAsync(60 * 60 * 1000) })
  expect(getWeather).toHaveBeenCalledTimes(2)
  visibility.mockReturnValue('visible')
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
  expect(getWeather).toHaveBeenCalledTimes(3)
})

it('uses a stale forecast only when supplied by the backend and clears it after a client network failure', async () => {
  vi.useFakeTimers()
  vi.mocked(getWeather).mockResolvedValueOnce({ ...resultFor('2026-09'), stale: true, warning: '上游暂不可用，使用缓存' })
    .mockRejectedValueOnce(new Error('网络断开'))
  const { result } = renderHook(() => useWeather('2026-09', true))
  await act(async () => undefined)
  expect(result.current.data?.stale).toBe(true)
  expect(result.current.data?.days['2026-09-09']?.description).toBe('小雨')
  await act(async () => { await vi.advanceTimersByTimeAsync(60 * 60 * 1000) })
  expect(result.current.data).toBeNull()
  expect(result.current.error).toBe('网络断开')
  await act(async () => { await vi.advanceTimersByTimeAsync(60 * 60 * 1000) })
  expect(result.current.error).toBeNull()
  expect(result.current.data?.month).toBe('2026-09')
})

it('refreshes at Hangzhou midnight before one hour has passed and clears yesterday while waiting', async () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-09-09T15:40:00Z')) // Hangzhou 23:40
  const next = deferred<WeatherResult>()
  vi.mocked(getWeather).mockResolvedValueOnce(resultFor('2026-09')).mockReturnValueOnce(next.promise)
  const { result } = renderHook(() => useWeather('2026-09', true))
  await act(async () => undefined)
  expect(result.current.data?.days['2026-09-09']).toBeDefined()
  await act(async () => { await vi.advanceTimersByTimeAsync(20 * 60 * 1000) })
  expect(getWeather).toHaveBeenCalledTimes(2)
  expect(result.current.data).toBeNull()
  expect(result.current.loading).toBe(true)
  const fresh = resultFor('2026-09')
  fresh.forecast_start = '2026-09-10'
  fresh.forecast_end = '2026-09-16'
  fresh.days = { '2026-09-10': resultFor('2026-09').days['2026-09-09'] }
  await act(async () => next.resolve(fresh))
  expect(result.current.data?.days['2026-09-09']).toBeUndefined()
  expect(result.current.data?.days['2026-09-10']).toBeDefined()
})

it('refreshes after a hidden midnight crossing even when the previous request is less than an hour old', async () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-09-09T15:40:00Z'))
  const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  const next = deferred<WeatherResult>()
  vi.mocked(getWeather).mockResolvedValueOnce(resultFor('2026-09')).mockReturnValueOnce(next.promise)
  const { result } = renderHook(() => useWeather('2026-09', true))
  await act(async () => undefined)
  visibility.mockReturnValue('hidden')
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
  await act(async () => { await vi.advanceTimersByTimeAsync(30 * 60 * 1000) }) // Hangzhou 00:10
  expect(getWeather).toHaveBeenCalledTimes(1)
  visibility.mockReturnValue('visible')
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
  expect(getWeather).toHaveBeenCalledTimes(2)
  expect(result.current.data).toBeNull()
  expect(result.current.loading).toBe(true)
})

it('waits for a hidden PC page to become visible before its first weather request', async () => {
  const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
  renderHook(() => useWeather('2026-09', true))
  expect(getWeather).not.toHaveBeenCalled()
  visibility.mockReturnValue('visible')
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
  expect(getWeather).toHaveBeenCalledTimes(1)
})
