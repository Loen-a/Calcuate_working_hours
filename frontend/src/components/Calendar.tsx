import { useMemo } from 'react'
import type { Day } from '../lib/types'
import { calendarDate, fmtDate, fmtMinutes, signedMinutes } from '../lib/format'

interface Props { selected: string; today: string; days: Day[]; busy: boolean; onPick: (date: string) => void }
const WEEK = ['一', '二', '三', '四', '五', '六', '日']
export default function Calendar({ selected, today, days, busy, onPick }: Props) {
  const [y, m] = selected.split('-').map(Number)
  const cells = useMemo(() => {
    const lead = (calendarDate(y, m - 1, 1).getDay() + 6) % 7
    return Array.from({ length: 42 }, (_, i) => {
      const value = calendarDate(y, m - 1, i - lead + 1)
      return { date: fmtDate(value.getFullYear(), value.getMonth() + 1, value.getDate()),
        day: value.getDate(), other: value.getMonth() + 1 !== m }
    })
  }, [y, m])
  const byDate = new Map(days.map(day => [day.date, day]))
  return (
    <section aria-label="工时日历">
      <div className="flex items-center gap-3 mb-3 text-[13px] text-ink-soft font-mono">
        <span className="uppercase tracking-[0.2em]">Log</span><span className="opacity-40">·</span><span>点击日期打卡 / 编辑</span>
      </div>
      <div className="border border-rule rounded-sm overflow-hidden bg-paper">
        <table className="w-full border-collapse table-fixed">
          <thead><tr>{WEEK.map((name, i) => <th key={name} className={`py-3 text-[13px] font-mono font-normal border-b border-rule bg-surface/60 ${i >= 5 ? 'text-plum' : 'text-ink-soft'}`}>{name}</th>)}</tr></thead>
          <tbody>{Array.from({ length: 6 }, (_, row) => <tr key={row}>
            {cells.slice(row * 7, row * 7 + 7).map(cell => {
              const day = byDate.get(cell.date)
              const rest = day && !day.is_workday
              return <td key={cell.date} className={`border border-rule p-0 align-top ${cell.other ? 'bg-rule/30' : rest ? 'bg-plum/[0.04]' : ''}`}>
                <button type="button" aria-label={`编辑 ${cell.date}`} aria-current={cell.date === today ? 'date' : undefined} disabled={busy} onClick={() => onPick(cell.date)}
                  className={`relative w-full min-h-[112px] sm:min-h-[120px] p-1.5 sm:p-2.5 text-left align-top hover:bg-surface transition-colors disabled:cursor-wait ${cell.date === selected ? 'outline outline-2 outline-navy -outline-offset-2' : cell.date === today ? 'outline outline-1 outline-ink -outline-offset-2' : ''}`}>
                  <div className="flex items-baseline justify-between gap-0.5">
                    <span className={`font-display text-[19px] sm:text-[20px] tabular-nums leading-none ${cell.other ? 'text-ink-soft/50' : rest ? 'text-plum' : 'text-ink'} ${cell.date === today ? 'font-semibold' : ''}`}>{cell.day}</span>
                    {day?.leave ? <span className="text-[11px] px-1 py-px bg-ochre/10 text-ochre rounded-sm">假</span>
                      : rest ? <span className="text-[11px] px-1 py-px bg-plum/10 text-plum rounded-sm">休</span>
                        : day?.manual_override === 'workday' ? <span className="text-[11px] px-1 py-px bg-navy/10 text-navy rounded-sm">班</span> : null}
                  </div>
                  <div className="text-[10px] sm:text-[12px] text-ink-soft mt-1.5 truncate">{day?.calendar_name || '\u00a0'}</div>
                  <div className="min-h-10 mt-2 font-mono text-[11px] sm:text-[13px] tabular-nums leading-snug">
                    {day?.actual_minutes != null ? <>
                      <div className="text-ink">{fmtMinutes(day.actual_minutes)}</div>
                      {day.daily_balance_minutes != null && <div className={day.daily_balance_minutes < 0 ? 'text-plum' : 'text-ochre'}>{signedMinutes(day.daily_balance_minutes)}</div>}
                    </> : day?.leave && day.entry ? <span className="text-ink-soft text-[10px]">打卡保留</span>
                      : day?.entry ? day.entry.start_time && day.entry.end_time
                        ? <span className="text-ink-soft text-[10px]" title="已记录 · 不计工时">已记录</span>
                        : <span className="text-ink-soft text-[10px]">待补全</span> : null}
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
