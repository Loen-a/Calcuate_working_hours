import { useEffect, useRef, useState } from 'react'
import type { DashboardData } from './lib/types'
import * as api from './lib/api'
import { fmtMinutes, shiftMonth } from './lib/format'
import { useAppliedTheme } from './lib/useTheme'
import { useAirQuality, useWeather } from './lib/useWeather'
import Header from './components/Header'
import Dashboard from './components/Dashboard'
import TrendChart from './components/TrendChart'
import Calendar from './components/Calendar'
import EntryModal from './components/EntryModal'
import Settings from './components/Settings'
import SelectedDayPanel from './components/SelectedDayPanel'

const messageOf = (error: unknown) => error instanceof Error ? error.message : String(error)
export default function App() {
  const initialDate = useRef(new URLSearchParams(window.location.search).get('reference_date') || '')
  const [data, setData] = useState<DashboardData | null>(null)
  const [modalDate, setModalDate] = useState<string | null>(null)
  const [busyKind, setBusyKind] = useState<string | null>('load')
  const busyRef = useRef<string | null>('load')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [fatal, setFatal] = useState('')
  const generation = useRef(0)
  useAppliedTheme(data?.theme || null)
  const weather = useWeather(data?.selected_date.slice(0, 7) || null, !fatal)
  const airQuality = useAirQuality(data?.selected_date.slice(0, 7) || null, !fatal)

  const applyDashboard = (next: DashboardData) => {
    setData(next)
    const url = new URL(window.location.href)
    url.searchParams.set('reference_date', next.selected_date)
    window.history.replaceState({}, '', url)
  }
  const reload = async (date: string) => {
    const token = ++generation.current
    const next = await api.getDashboard(date)
    if (token === generation.current) applyDashboard(next)
    return next
  }
  useEffect(() => {
    let alive = true
    api.getDashboard(initialDate.current)
      .then(next => { if (alive) applyDashboard(next) })
      .catch(error => { if (alive) setFatal('无法读取工时数据：' + messageOf(error)) })
      .finally(() => { if (alive) { busyRef.current = null; setBusyKind(null) } })
    return () => { alive = false }
  }, [])

  const navigate = async (date: string, open = false) => {
    if (busyRef.current) return
    busyRef.current = 'load'; setBusyKind('load'); setError(''); setNotice('')
    try {
      const next = await reload(date)
      setModalDate(open ? next.selected_date : null)
    } catch (error) { setError(messageOf(error)) }
    finally { busyRef.current = null; setBusyKind(null) }
  }
  const mutate = async <T,>(kind: string, action: () => Promise<T>, dateAfter?: (result: T) => string): Promise<T> => {
    if (busyRef.current) throw new Error('正在处理其他操作，请稍候')
    busyRef.current = kind; setBusyKind(kind); setError(''); setNotice('')
    try {
      const result = await action()
      try { await reload(dateAfter ? dateAfter(result) : data!.selected_date) }
      catch (error) {
        const label = kind === 'import' ? '导入' : '操作'
        setFatal(`${label}已完成，但重新读取失败：${messageOf(error)}。请刷新页面后继续。`)
        throw error
      }
      return result
    } finally { busyRef.current = null; setBusyKind(null) }
  }
  const handleImport = async (file: File) => {
    if (busyRef.current) return
    if (!window.confirm('导入将覆盖现有打卡、统计设置、非工作时段、日历和请假数据（旧版备份未包含的设置保留）。建议先导出备份。确定继续？')) return
    try {
      const result = await mutate('import', () => api.importBackup(file))
      setNotice(`导入成功，共 ${result.entries} 条记录`)
    } catch (error) { setError('导入失败：' + messageOf(error)) }
  }
  const handleRefresh = async () => {
    try {
      const status = await mutate('holidays', () => api.refreshHolidays(data!.holiday_status.year))
      if (status.warning) setError(status.warning)
      else setNotice(`${status.year} 年节假日已刷新`)
    } catch (error) { setError('刷新失败：' + messageOf(error)) }
  }
  const handleClock = async (kind: 'in' | 'out') => {
    try {
      await mutate('clock', () => api.clock(kind), result => result.date)
      setNotice(kind === 'in' ? '已记录当前上班时间' : '已记录当前下班时间')
    } catch (error) { setError(messageOf(error)) }
  }
  if (fatal) return <main className="min-h-screen flex flex-col items-center justify-center gap-5 px-6 text-center">
    <p role="alert" className="text-plum">{fatal}</p>
    <button className="border border-rule rounded-sm px-5 py-3" onClick={() => window.location.reload()}>重新加载</button>
    <a href={'/interface/old?reference_date=' + encodeURIComponent(data?.selected_date || initialDate.current)}>切换旧界面</a>
  </main>
  if (!data) return <div className="min-h-screen grid place-items-center">正在连接本地数据库…</div>
  const busy = busyKind !== null
  const visibleTheme = data.theme
  const nextTheme = visibleTheme === 'cool' ? 'teal' : visibleTheme === 'teal' ? 'classic' : 'cool'
  const day = modalDate ? data.days.find(day => day.date === modalDate) : null
  const selectedDay = data.days.find(day => day.date === data.selected_date)
  const { holiday_status: holiday, forecast } = data
  const sourceLabel = holiday.source === 'fallback' ? '按星期规则计算' : holiday.source === 'cache' ? '本地缓存' : '已从 holiday-cn 获取'
  return (
    <div className="workhours-app min-h-screen">
      <Header date={data.selected_date} theme={visibleTheme} busy={busy} importBusy={busyKind === 'import'}
        onPrev={() => void navigate(shiftMonth(data.selected_date, -1))} onNext={() => void navigate(shiftMonth(data.selected_date, 1))}
        onToday={() => void navigate(data.today)} onExport={api.downloadBackup} onImport={file => void handleImport(file)}
        onThemeToggle={() => { void mutate('theme', () => api.putSettings({ theme: nextTheme })).catch(error => setError('主题保存失败：' + messageOf(error))) }} />
      <main className="workhours-content max-w-5xl mx-auto px-8 py-12" aria-busy={busy}>
        {error && <p role="alert" className="mb-5 p-3 bg-plum/10 border border-plum/30 rounded-sm text-plum text-[13px]">{error}</p>}
        {notice && <p role="status" className="mb-5 p-3 bg-navy/10 border border-navy/30 rounded-sm text-navy text-[13px]">{notice}</p>}
        <div className="workhours-toolbar flex flex-wrap items-center justify-between gap-3 mb-6">
          <label className="workhours-label text-[13px] text-ink-soft">查看日期
            <input type="date" aria-label="查看日期" value={data.selected_date} disabled={busy} className="ml-3 bg-surface border border-rule rounded-sm px-2 py-2 font-mono text-ink" onChange={event => { if (event.target.value) void navigate(event.target.value) }} />
          </label>
          <div className="flex flex-wrap gap-2">
            <button disabled={busy} onClick={() => void handleClock('in')} className="workhours-primary-action bg-ink text-paper px-3 py-2 rounded-sm text-[13px] disabled:opacity-40">现在上班</button>
            <button disabled={busy} onClick={() => void handleClock('out')} className="workhours-secondary-action border border-ink px-3 py-2 rounded-sm text-[13px] disabled:opacity-40">现在下班</button>
          </div>
        </div>
        <Dashboard data={data} />
        <p className="workhours-period-summary workhours-help mt-4 text-[12px] text-ink-soft font-mono leading-relaxed">
          当前{data.settings.period === 'week' ? '周' : '月'}周期 {forecast.period_start} — {forecast.period_end} · 目标 {fmtMinutes(forecast.target_minutes)} · 已完成 {fmtMinutes(forecast.completed_minutes)} · 待完成 {fmtMinutes(forecast.remaining_target_minutes)}
        </p>
        <div className="workhours-workspace">
          <Calendar selected={data.selected_date} today={data.today} days={data.days} busy={busy} weather={weather} airQuality={airQuality} onPick={date => void navigate(date)} />
          {selectedDay && <SelectedDayPanel day={selectedDay} preview={data.selected_preview} today={data.today}
            busy={busy} onEdit={() => setModalDate(data.selected_date)} />}
        </div>
        {data.month.missing_history_days.length > 0 && <div className="mt-5 flex items-start gap-3 bg-ochre/10 border border-ochre/30 rounded-sm px-4 py-3">
          <span className="workhours-label text-ochre font-mono text-[12px] shrink-0">提醒</span>
          <span className="workhours-body text-[13px] font-mono">本月还有 {data.month.missing_history_days.length} 个工作日未完成打卡：
            {data.month.missing_history_days.slice(0, 5).map(date => date.slice(5)).join('、')}{data.month.missing_history_days.length > 5 ? '…' : ''}</span>
        </div>}
        <TrendChart days={data.days} />
        <Settings data={data} busy={busy} onPeriod={async period => { await mutate('settings', () => api.putSettings({ period })) }}
          onSave={async interval => { await mutate('interval', () => api.saveInterval(interval)) }} onDelete={async id => { await mutate('interval', () => api.deleteInterval(id)) }} />
        <div className="workhours-calendar-source workhours-help mt-6 text-center text-[12px] text-ink-soft font-mono leading-relaxed">
          <p>{holiday.year} 年节假日 · {sourceLabel} · 数据保存在本地数据库</p>
          {holiday.warning && <p className="text-ochre mt-1">{holiday.warning}</p>}
          <button disabled={busy} onClick={() => void handleRefresh()} className="mt-3 border border-rule px-4 py-2 rounded-full hover:border-ink-soft disabled:opacity-40">{busyKind === 'holidays' ? '刷新中…' : '刷新节假日'}</button>
        </div>
      </main>
      {day && <EntryModal key={day.date} day={day} preview={data.selected_preview} externalBusy={busy} onClose={() => setModalDate(null)}
        onSave={async entry => { await mutate('entry', () => api.putEntry(day.date, entry)) }}
        onDelete={async () => { await mutate('entry', () => api.deleteEntry(day.date)) }}
        onLeave={async enabled => { await mutate('leave', () => api.setLeave(day.date, enabled)) }}
        onCalendar={async kind => { await mutate('calendar', () => api.setCalendar(day.date, kind)) }} />}
    </div>
  )
}
