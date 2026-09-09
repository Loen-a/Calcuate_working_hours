import { useEffect, useState } from 'react'
import { getAirQuality, getWeather } from './api'
import type { AirQualityState, WeatherState } from './types'

const HOUR = 60 * 60 * 1000
const DAY = 24 * HOUR
const HANGZHOU_OFFSET = 8 * HOUR
const hangzhouDay = (timestamp: number) => Math.floor((timestamp + HANGZHOU_OFFSET) / DAY)
const empty = { data: null, loading: false, error: null }

interface Forecast { month: string; forecast_start: string; forecast_end: string; days: Record<string, unknown> }
interface ForecastState<T> { data: T | null; loading: boolean; error: string | null }

export function useWeather(month: string | null, enabled: boolean): WeatherState {
  return useForecast(month, enabled, getWeather)
}

export function useAirQuality(month: string | null, enabled: boolean): AirQualityState {
  return useForecast(month, enabled, getAirQuality)
}

// 两个接口各自维护结果和刷新时钟；AQI 延迟、失败不会清除已经显示的天气。
function useForecast<T extends Forecast>(month: string | null, enabled: boolean,
  fetchForecast: (month: string, signal?: AbortSignal) => Promise<T>): ForecastState<T> {
  const [state, setState] = useState<ForecastState<T> & { month: string | null }>({ ...empty, month: null })
  useEffect(() => {
    if (!enabled || !month) {
      setState({ ...empty, month: null })
      return
    }
    let alive = true
    let controller: AbortController | null = null
    let lastAttempt: number | null = null
    let timer: number | undefined
    const scheduleNext = () => {
      window.clearTimeout(timer)
      const now = Date.now()
      const untilMidnight = (hangzhouDay(now) + 1) * DAY - HANGZHOU_OFFSET - now
      timer = window.setTimeout(() => {
        if (!alive) return
        if (document.visibilityState === 'visible') void refresh()
        else scheduleNext()
      }, Math.min(HOUR, untilMidnight))
    }
    const refresh = async () => {
      if (!alive) return
      controller?.abort()
      const request = new AbortController()
      controller = request
      lastAttempt = Date.now()
      scheduleNext()
      setState({ month, data: null, loading: true, error: null })
      try {
        const data = await fetchForecast(month, request.signal)
        if (!alive || request.signal.aborted) return
        if (!data || data.month !== month || !data.days || typeof data.days !== 'object'
          || typeof data.forecast_start !== 'string' || typeof data.forecast_end !== 'string') {
          throw new Error('天气数据格式无效')
        }
        setState({ month, data, loading: false, error: null })
      } catch (error) {
        if (!alive || request.signal.aborted) return
        // Only the API may provide a validated stale forecast; discard failed client requests.
        setState({ month, data: null, loading: false, error: error instanceof Error ? error.message : String(error) })
      }
    }
    if (document.visibilityState === 'visible') void refresh()
    else {
      setState({ ...empty, month })
      scheduleNext()
    }
    const onVisible = () => {
      const now = Date.now()
      if (document.visibilityState === 'visible' && (lastAttempt === null
        || now - lastAttempt >= HOUR || hangzhouDay(now) !== hangzhouDay(lastAttempt))) void refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      alive = false
      controller?.abort()
      window.clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [month, enabled, fetchForecast])

  // A month change must hide the previous result before its replacement effect runs.
  return enabled && month && state.month === month ? state : empty
}
