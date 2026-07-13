import { useEffect, useMemo, useRef, useState } from 'react'
import type { Entries, HolidayMap, HolidaySource, Theme, WorkEntry } from './lib/types'
import { dayInfo } from './lib/holidays'
import { calcNet, fmtDate } from './lib/workHours'
import {
  deleteEntry,
  downloadBackup,
  getEntries,
  getHolidays,
  getPreferences,
  importBackup,
  putEntry,
  putPreferences,
} from './lib/api'
import { useAppliedTheme } from './lib/useTheme'
import Header from './components/Header'
import Dashboard from './components/Dashboard'
import TrendChart from './components/TrendChart'
import Calendar from './components/Calendar'
import EntryModal from './components/EntryModal'

export default function App() {
  const now = new Date()
  const [viewY, setViewY] = useState(now.getFullYear())
  const [viewM, setViewM] = useState(now.getMonth() + 1)
  const viewYRef = useRef(now.getFullYear())
  const holidayRequestGeneration = useRef(0)
  const mutationRef = useRef<'entry' | 'theme' | 'import' | null>(null)
  const [entries, setEntries] = useState<Entries>({})
  const [hMap, setHMap] = useState<HolidayMap | undefined>(undefined)
  const [holidaySource, setHolidaySource] = useState<HolidaySource | null>(null)
  const [theme, setTheme] = useState<Theme | null>(null)
  const [mutationKind, setMutationKind] = useState<'entry' | 'theme' | 'import' | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [recoveryError, setRecoveryError] = useState('')
  const [modalDate, setModalDate] = useState<string | null>(null)

  useAppliedTheme(theme)

  const runMutation = async <T,>(
    kind: 'entry' | 'theme' | 'import',
    action: () => Promise<T>,
  ): Promise<T> => {
    if (mutationRef.current !== null) throw new Error('正在处理其他数据操作，请稍候')
    mutationRef.current = kind
    setMutationKind(kind)
    try {
      return await action()
    } finally {
      mutationRef.current = null
      setMutationKind(null)
    }
  }

  useEffect(() => {
    let alive = true
    Promise.all([getEntries(), getPreferences()])
      .then(([loadedEntries, preferences]) => {
        if (!alive) return
        setEntries(loadedEntries)
        setTheme(preferences.theme)
        setLoading(false)
      })
      .catch((error) => {
        if (!alive) return
        setLoadError(error instanceof Error ? error.message : String(error))
        setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    let alive = true
    const generation = ++holidayRequestGeneration.current
    setHMap(undefined)
    setHolidaySource(null)
    getHolidays(viewY)
      .then((result) => {
        if (
          !alive ||
          generation !== holidayRequestGeneration.current ||
          viewYRef.current !== viewY
        ) return
        setHMap(result.holidays)
        setHolidaySource(result.source)
      })
      .catch((error) => {
        if (
          !alive ||
          generation !== holidayRequestGeneration.current ||
          viewYRef.current !== viewY
        ) return
        setLoadError(error instanceof Error ? error.message : String(error))
      })
    return () => {
      alive = false
    }
  }, [viewY])

  const navMonth = (delta: number) => {
    if (mutationRef.current === 'import') return
    let nm = viewM + delta
    let ny = viewY
    if (nm < 1) {
      nm = 12
      ny--
    } else if (nm > 12) {
      nm = 1
      ny++
    }
    viewYRef.current = ny
    setViewY(ny)
    setViewM(nm)
  }
  const goToday = () => {
    if (mutationRef.current === 'import') return
    const t = new Date()
    viewYRef.current = t.getFullYear()
    setViewY(t.getFullYear())
    setViewM(t.getMonth() + 1)
  }

  const handlePick = (date: string) => {
    if (mutationRef.current === 'import') return
    const [py, pm] = date.split('-').map(Number)
    if (py !== viewY || pm !== viewM) {
      viewYRef.current = py
      setViewY(py)
      setViewM(pm)
      return
    }
    setModalDate(date)
  }

  const upsert = async (date: string, entry: WorkEntry | null) => {
    await runMutation('entry', async () => {
      if (entry) {
        const saved = await putEntry(date, entry)
        setEntries((prev) => ({ ...prev, [date]: saved }))
      } else {
        await deleteEntry(date)
        setEntries((prev) => {
          const next = { ...prev }
          delete next[date]
          return next
        })
      }
    })
  }

  const handleThemeToggle = async () => {
    if (mutationRef.current !== null) return
    const nextTheme: Theme = theme === 'cool' ? 'teal' : 'cool'
    try {
      const saved = await runMutation('theme', () => putPreferences(nextTheme))
      setTheme(saved.theme)
    } catch (error) {
      window.alert('主题保存失败：' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const handleExport = () => downloadBackup()

  const handleImport = async (file: File) => {
    if (mutationRef.current !== null) return
    if (
      Object.keys(entries).length > 0 &&
      !window.confirm('导入会覆盖数据库中的现有数据，确定？')
    ) return
    if (mutationRef.current !== null) return
    try {
      const summary = await runMutation('import', async () => {
        const imported = await importBackup(file)
        try {
          const reloadYear = viewYRef.current
          const holidayGeneration = ++holidayRequestGeneration.current
          const [loadedEntries, preferences, holidays] = await Promise.all([
            getEntries(),
            getPreferences(),
            getHolidays(reloadYear),
          ])
          if (
            holidayGeneration !== holidayRequestGeneration.current ||
            viewYRef.current !== reloadYear
          ) throw new Error('查看年份已变化，无法提交重新读取的数据')
          setEntries(loadedEntries)
          setTheme(preferences.theme)
          setHMap(holidays.holidays)
          setHolidaySource(holidays.source)
        } catch (error) {
          setRecoveryError(error instanceof Error ? error.message : String(error))
          return null
        }
        return imported
      })
      if (summary !== null) window.alert('导入成功，共 ' + summary.entries + ' 条记录')
    } catch (error) {
      window.alert('导入失败：' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const note = holidaySource === null
    ? '正在加载节假日数据 · 数据存于本地数据库'
    : holidaySource === 'fallback'
      ? `${viewY} 年节假日数据未获取到，已按周末推断 · 数据存于本地数据库`
      : holidaySource === 'cache'
        ? '节假日数据: holiday-cn（本地缓存） · 数据存于本地数据库'
        : '节假日数据: holiday-cn · 数据存于本地数据库'

  // 提醒：当月、已过去的（不含今天）工作日里没打卡的日期
  const missedPast: string[] = useMemo(() => {
    const t = new Date()
    if (viewY !== t.getFullYear() || viewM !== t.getMonth() + 1) return []
    if (!hMap) return []
    const list: string[] = []
    for (let d = 1; d < t.getDate(); d++) {
      if (dayInfo(viewY, viewM, d, hMap).type === 'work') {
        const e = entries[fmtDate(viewY, viewM, d)]
        if (!e || calcNet(e.in, e.out) == null) list.push(fmtDate(viewY, viewM, d))
      }
    }
    return list
  }, [viewY, viewM, hMap, entries])

  if (recoveryError) {
    return (
      <div className="min-h-screen grid place-items-center text-plum px-6 text-center">
        导入已完成，但重新读取失败：{recoveryError}。请刷新页面或重新连接本地数据库。
      </div>
    )
  }
  if (loadError) {
    return (
      <div className="min-h-screen grid place-items-center text-plum">
        无法连接本地数据库：{loadError}
      </div>
    )
  }
  if (loading || theme === null) {
    return <div className="min-h-screen grid place-items-center">正在连接本地数据库…</div>
  }

  return (
    <div className="min-h-screen">
      <Header
        y={viewY}
        m={viewM}
        theme={theme}
        themeBusy={mutationKind !== null}
        importBusy={mutationKind === 'import'}
        onPrev={() => navMonth(-1)}
        onNext={() => navMonth(1)}
        onToday={goToday}
        onThemeToggle={handleThemeToggle}
        onExport={handleExport}
        onImport={handleImport}
      />
      <main className="max-w-5xl mx-auto px-8 py-12 sm:py-16">
        <Dashboard y={viewY} m={viewM} entries={entries} hMap={hMap} />
        <div className="my-10 h-px bg-rule" />
        <TrendChart y={viewY} m={viewM} entries={entries} hMap={hMap} />
        <div className="mt-10 mb-4 h-px bg-rule" />
        <Calendar y={viewY} m={viewM} entries={entries} hMap={hMap} onPick={handlePick} />
        {missedPast.length > 0 && (
          <div className="mt-5 flex items-start gap-3 bg-ochre/10 border border-ochre/30 rounded-sm px-4 py-3">
            <span className="text-ochre font-mono uppercase tracking-[0.14em] text-[11px] font-medium shrink-0 mt-0.5">
              提醒
            </span>
            <span className="text-ink text-[13px] font-mono tabular-nums">
              本月还有 {missedPast.length} 个工作日未打卡：
              {missedPast
                .slice(0, 5)
                .map((d) => d.slice(5))
                .join('、')}
              {missedPast.length > 5 && ` 等 ${missedPast.length} 个`}
            </span>
          </div>
        )}
        <p className="text-center text-[13px] tracking-wide text-ink-soft mt-6 font-mono">{note}</p>
      </main>
      {modalDate && (
        <EntryModal
          date={modalDate}
          entry={entries[modalDate]}
          isRestDay={!!hMap && dayInfo(viewY, viewM, parseInt(modalDate.split('-')[2], 10), hMap).type === 'rest'}
          externalBusy={mutationKind !== null}
          onClose={() => setModalDate(null)}
          onSave={async (e) => {
            await upsert(modalDate, e)
            setModalDate(null)
          }}
          onDelete={async () => {
            await upsert(modalDate, null)
            setModalDate(null)
          }}
        />
      )}
    </div>
  )
}
