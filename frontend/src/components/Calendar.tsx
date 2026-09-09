import { useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import type { AirQualityState, Day, WeatherState } from '../lib/types'
import WeatherDay from './WeatherDay'
import { calendarDate, fmtDate, fmtMinutes, signedMinutes } from '../lib/format'

interface Props { selected: string; today: string; days: Day[]; busy: boolean; weather?: WeatherState; airQuality?: AirQualityState; onPick: (date: string) => void }
const WEEK = ['一', '二', '三', '四', '五', '六', '日']
export default function Calendar({ selected, today, days, busy, weather, airQuality, onPick }: Props) {
  const calendarRef = useRef<HTMLElement>(null)
  const pendingFocus = useRef<{ origin: HTMLButtonElement; cancelled: boolean } | null>(null)
  useEffect(() => {
    const handleFocus = (event: FocusEvent) => {
      const pending = pendingFocus.current
      if (pending && event.target !== pending.origin && event.target !== document.body && event.target !== document.documentElement) {
        pending.cancelled = true
      }
    }
    document.addEventListener('focusin', handleFocus)
    return () => document.removeEventListener('focusin', handleFocus)
  }, [])
  useLayoutEffect(() => {
    const pending = pendingFocus.current
    if (busy || !pending) return
    pendingFocus.current = null
    const active = document.activeElement
    // Restore only a calendar-initiated request whose focus was lost to disabling.
    if (!pending.cancelled && (active === document.body || active === document.documentElement || active === pending.origin)) {
      calendarRef.current?.querySelector<HTMLButtonElement>('button[aria-pressed="true"]')?.focus()
    }
  })
  const [y, m] = selected.split('-').map(Number)
  const monthDays = calendarDate(y, m, 0).getDate()
  const cells = useMemo(() => {
    const lead = (calendarDate(y, m - 1, 1).getDay() + 6) % 7
    const cellCount = Math.ceil((lead + monthDays) / 7) * 7
    return Array.from({ length: cellCount }, (_, i) => {
      const value = calendarDate(y, m - 1, i - lead + 1)
      return { date: fmtDate(value.getFullYear(), value.getMonth() + 1, value.getDate()),
        day: value.getDate(), other: value.getMonth() + 1 !== m }
    })
  }, [y, m, monthDays])
  const byDate = new Map(days.map(day => [day.date, day]))
  const forecast = weather?.data?.month === selected.slice(0, 7) ? weather.data : null
  const airForecast = airQuality?.data?.standard === 'US' && airQuality.data.month === selected.slice(0, 7) ? airQuality.data : null
  const weatherNote = weather?.loading ? '天气加载中…'
    : weather?.error ? '天气暂不可用，稍后自动重试'
      : forecast?.stale ? '缓存天气待更新'
        : forecast?.source === 'unavailable' && forecast.warning ? forecast.warning : null
  return (
    <section ref={calendarRef} className="workhours-calendar workhours-calendar--desktop" aria-label="工时日历">
      <div className="workhours-calendar-heading">
        <div>
          <h2 className="workhours-section-title">工时日历</h2>
          <p className="workhours-calendar-range workhours-help">{fmtDate(y, m, 1)} — {fmtDate(y, m, monthDays)}</p>
          {weather && <div className="workhours-weather-heading">
            <span>杭州</span><span>7天预报（°C）</span>
            <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>
            <a href="https://atmosphere.copernicus.eu/" target="_blank" rel="noreferrer">CAMS</a>
            <span>日均湿度 · 日最高AQI（美标）</span>
            {weatherNote && <span className="workhours-weather-note" aria-live="polite" title={weather.error || forecast?.warning || undefined}>{weatherNote}</span>}
            {airForecast?.stale && <span className="workhours-weather-note" title={airForecast.warning || undefined}>空气质量缓存待更新</span>}
          </div>}
        </div>
        <div className="workhours-calendar-legend" aria-label="日历标记">
          <span data-kind="workday">工作日</span>
          <span data-kind="rest">休息日</span>
          <span data-kind="leave">全天请假</span>
        </div>
      </div>
      <div className="workhours-calendar-grid border border-rule rounded-sm overflow-hidden bg-paper">
        <table className="workhours-calendar-table w-full border-collapse table-fixed">
          <thead><tr>{WEEK.map((name, i) => <th key={name} className={`py-3 text-[13px] font-mono font-normal border-b border-rule bg-surface/60 ${i >= 5 ? 'text-plum' : 'text-ink-soft'}`}>{name}</th>)}</tr></thead>
          <tbody>{Array.from({ length: cells.length / 7 }, (_, row) => <tr key={row}>
            {cells.slice(row * 7, row * 7 + 7).map(cell => {
              const day = byDate.get(cell.date)
              const rest = day && !day.is_workday
              const dayWeather = forecast && cell.date >= forecast.forecast_start && cell.date <= forecast.forecast_end
                ? forecast.days[cell.date] : undefined
              const dayAir = airForecast && cell.date >= airForecast.forecast_start && cell.date <= airForecast.forecast_end
                ? airForecast.days[cell.date] : undefined
              return <td key={cell.date} className={`border border-rule p-0 align-top ${cell.other ? 'bg-rule/30' : rest ? 'bg-plum/[0.04]' : ''}`}>
                <button type="button" aria-label={`选择 ${cell.date}`} aria-describedby={dayWeather ? `weather-${cell.date}` : undefined} aria-pressed={cell.date === selected} aria-current={cell.date === today ? 'date' : undefined} disabled={busy} onClick={event => {
                  pendingFocus.current = { origin: event.currentTarget, cancelled: false }
                  onPick(cell.date)
                }}
                  className={`workhours-calendar-cell relative w-full min-h-[120px] p-2.5 text-left align-top hover:bg-surface transition-colors disabled:cursor-wait ${dayWeather ? 'workhours-calendar-cell--weather' : ''} ${cell.date === selected ? 'outline outline-2 outline-navy -outline-offset-2' : cell.date === today ? 'outline outline-1 outline-ink -outline-offset-2' : ''}`}>
                  <div className="workhours-calendar-date-row flex items-baseline justify-between gap-0.5">
                    <span className={`workhours-calendar-date font-display text-[20px] tabular-nums leading-none ${cell.other ? 'text-ink-soft/50' : rest ? 'text-plum' : 'text-ink'} ${cell.date === today ? 'font-semibold' : ''}`}>{cell.day}</span>
                    {day?.leave ? <span className="workhours-calendar-badge text-[11px] px-1 py-px bg-ochre/10 text-ochre rounded-sm">假</span>
                      : rest ? <span className="workhours-calendar-badge text-[11px] px-1 py-px bg-plum/10 text-plum rounded-sm">休</span>
                        : day?.manual_override === 'workday' ? <span className="workhours-calendar-badge text-[11px] px-1 py-px bg-navy/10 text-navy rounded-sm">班</span> : null}
                  </div>
                  {<WeatherDay id={`weather-${cell.date}`} weather={dayWeather} airQuality={dayAir} airLoading={airQuality?.loading} airStale={airForecast?.stale} />}
                  <div className={`workhours-calendar-name text-[12px] text-ink-soft mt-1.5 truncate ${weather ? 'workhours-calendar-name--weather' : ''}`}>
                    {weather ? <>
                      <span className="workhours-calendar-name-text" title={day?.calendar_name}>{day?.calendar_name || '\u00a0'}</span>
                    </> : day?.calendar_name || '\u00a0'}
                  </div>
                  <div className="workhours-calendar-record min-h-10 mt-2 font-mono text-[13px] tabular-nums leading-snug">
                    {day?.actual_minutes != null ? <>
                      <div className="workhours-calendar-hours text-ink">{fmtMinutes(day.actual_minutes)}</div>
                      {day.daily_balance_minutes != null && <div data-balance-sign={day.daily_balance_minutes > 0 ? 'positive' : day.daily_balance_minutes < 0 ? 'negative' : 'zero'} className={`workhours-calendar-balance ${day.daily_balance_minutes < 0 ? 'text-plum' : 'text-ochre'}`}>{signedMinutes(day.daily_balance_minutes)}</div>}
                    </> : day?.leave && day.entry ? <span className="workhours-calendar-status text-ink-soft text-[10px]">打卡保留</span>
                      : day?.entry ? day.entry.start_time && day.entry.end_time
                        ? <span className="workhours-calendar-status text-ink-soft text-[10px]" title="已记录 · 不计工时">已记录</span>
                        : <span className="workhours-calendar-status text-ink-soft text-[10px]">待补全</span> : null}
                  </div>
                </button>
              </td>
            })}
          </tr>)}</tbody>
        </table>
      </div>
    </section>
  )
}
