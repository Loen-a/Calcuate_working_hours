import { useEffect, useMemo, useState } from 'react'
import type { Entries, HolidayMap } from './lib/types'
import { loadEntries, saveEntries } from './lib/storage'
import { fetchHolidays, dayInfo } from './lib/holidays'
import { calcNet, fmtDate } from './lib/workHours'
import { downloadExport, parseImport } from './lib/backup'
import Header from './components/Header'
import Dashboard from './components/Dashboard'
import TrendChart from './components/TrendChart'
import Calendar from './components/Calendar'
import EntryModal from './components/EntryModal'

export default function App() {
  const now = new Date()
  const [viewY, setViewY] = useState(now.getFullYear())
  const [viewM, setViewM] = useState(now.getMonth() + 1)
  const [entries, setEntries] = useState<Entries>(() => loadEntries())
  const [hMap, setHMap] = useState<HolidayMap | undefined>(undefined)
  const [modalDate, setModalDate] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchHolidays(viewY).then((map) => {
      if (alive) setHMap(map)
    })
    return () => {
      alive = false
    }
  }, [viewY])

  const navMonth = (delta: number) => {
    let nm = viewM + delta
    let ny = viewY
    if (nm < 1) {
      nm = 12
      ny--
    } else if (nm > 12) {
      nm = 1
      ny++
    }
    setViewY(ny)
    setViewM(nm)
  }
  const goToday = () => {
    const t = new Date()
    setViewY(t.getFullYear())
    setViewM(t.getMonth() + 1)
  }

  const handlePick = (date: string) => {
    const [py, pm] = date.split('-').map(Number)
    if (py !== viewY || pm !== viewM) {
      setViewY(py)
      setViewM(pm)
      return
    }
    setModalDate(date)
  }

  const upsert = (date: string, e: { in: string; out: string } | null) => {
    setEntries((prev) => {
      const next = { ...prev }
      if (e && e.in && e.out) next[date] = e
      else delete next[date]
      saveEntries(next)
      return next
    })
  }

  // 导出：触发浏览器下载（保存位置由浏览器/用户在 Save As 里决定）
  const handleExport = () => {
    downloadExport()
  }

  // 导入：覆盖当前所有 entries（如果已有数据先 confirm 一下）
  const handleImport = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const imported = parseImport(String(reader.result))
        const count = Object.keys(entries).length
        if (count > 0 && !window.confirm(`导入会覆盖当前 ${count} 条打卡记录，确定？`)) return
        setEntries(imported)
        saveEntries(imported)
        window.alert(`导入成功，共 ${Object.keys(imported).length} 条记录`)
      } catch (e) {
        window.alert('导入失败：' + (e instanceof Error ? e.message : String(e)))
      }
    }
    reader.readAsText(file)
  }

  const note = !hMap
    ? '数据存于本地浏览器'
    : Object.keys(hMap).length > 0
      ? '节假日数据: holiday-cn · 数据存于本地浏览器'
      : `${viewY} 年节假日数据未获取到，已按周末推断 · 数据存于本地浏览器`

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

  return (
    <div className="min-h-screen">
      <Header
        y={viewY}
        m={viewM}
        onPrev={() => navMonth(-1)}
        onNext={() => navMonth(1)}
        onToday={goToday}
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
          onClose={() => setModalDate(null)}
          onSave={(e) => {
            upsert(modalDate, e)
            setModalDate(null)
          }}
          onDelete={() => {
            upsert(modalDate, null)
            setModalDate(null)
          }}
        />
      )}
    </div>
  )
}
