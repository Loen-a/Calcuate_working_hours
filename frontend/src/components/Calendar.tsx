import { useMemo } from 'react'
import type { Entries, HolidayMap } from '../lib/types'
import { dayInfo } from '../lib/holidays'
import { calcNet, DAILY_TARGET, fmtDate, fmtDuration, floorTo30Min, isEntryCounted } from '../lib/workHours'

interface Props {
  y: number
  m: number
  entries: Entries
  hMap?: HolidayMap
  onPick: (d: string) => void
}

const WEEK = ['一', '二', '三', '四', '五', '六', '日']

interface Cell {
  y: number
  m: number
  d: number
  other: boolean
}

export default function Calendar({ y, m, entries, hMap, onPick }: Props) {
  const cells = useMemo<Cell[]>(() => {
    const first = new Date(y, m - 1, 1)
    const lead = (first.getDay() + 6) % 7 // 周一开头
    const daysInMonth = new Date(y, m, 0).getDate()
    const prevDays = new Date(y, m - 1, 0).getDate()
    const arr: Cell[] = []
    for (let i = lead - 1; i >= 0; i--) {
      const d = prevDays - i
      const pm = m - 1
      arr.push({ y: pm < 1 ? y - 1 : y, m: pm < 1 ? 12 : pm, d, other: true })
    }
    for (let d = 1; d <= daysInMonth; d++) arr.push({ y, m, d, other: false })
    let nx = 1
    while (arr.length < 42) {
      const nm = m + 1
      arr.push({ y: nm > 12 ? y + 1 : y, m: nm > 12 ? 1 : nm, d: nx++, other: true })
    }
    return arr
  }, [y, m])

  const today = new Date()
  const isCurMonth = today.getFullYear() === y && today.getMonth() + 1 === m

  return (
    <section>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-[13px] uppercase tracking-[0.2em] text-ink-soft font-mono">Log</span>
        <span className="text-ink-soft/40 font-mono">·</span>
        <span className="text-[13px] tracking-[0.2em] text-ink-soft font-mono">
          点击日期打卡 / 编辑
        </span>
      </div>
      <div className="border border-rule rounded-sm overflow-hidden bg-paper">
        <table className="w-full border-collapse [table-layout:fixed]">
          <thead>
            <tr>
              {WEEK.map((n, i) => (
                <th
                  key={n}
                  className={`py-3 text-[13px] uppercase tracking-[0.16em] font-mono font-normal border-b border-rule bg-surface/60 ${
                    i >= 5 ? 'text-plum' : 'text-ink-soft'
                  }`}
                >
                  {n}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 6 }).map((_, r) => (
              <tr key={r}>
                {cells.slice(r * 7, r * 7 + 7).map((c) => {
                  const info = dayInfo(c.y, c.m, c.d, c.y === y ? hMap : undefined)
                  const key = fmtDate(c.y, c.m, c.d)
                  const e = entries[key]
                  const net = e ? calcNet(e.in, e.out) : null
                  const ot = net != null ? net - DAILY_TARGET : 0
                  const isToday = isCurMonth && !c.other && c.d === today.getDate()
                  const isRest = info.type === 'rest'
                  const isCounted = e ? isEntryCounted(e.counts, !isRest) : false
                  const shownNet = isCounted && isRest ? floorTo30Min(net!) : net!
                  const netColor = isCounted
                    ? ot > 0
                      ? 'text-ochre'
                      : ot < 0
                        ? 'text-plum'
                        : 'text-ink'
                    : 'text-ink-soft'
                  return (
                    <td
                      key={key}
                      onClick={() => onPick(key)}
                      className={`relative border border-rule align-top p-2.5 cursor-pointer h-[100px] hover:bg-surface transition-colors
                        ${c.other ? 'bg-rule/30' : ''}
                        ${!c.other && isRest ? 'bg-plum/[0.04]' : ''}
                        ${isToday ? 'outline outline-1 outline-ink -outline-offset-2 z-10' : ''}`}
                    >
                      <div className="flex items-baseline justify-between gap-1">
                        <span
                          className={`font-display text-[20px] tabular-nums leading-none ${
                            !c.other && isRest
                              ? 'text-plum'
                              : c.other
                                ? 'text-ink-soft/50'
                                : 'text-ink'
                          } ${isToday ? 'font-semibold' : ''}`}
                        >
                          {c.d}
                        </span>
                        <div className="flex gap-1 shrink-0">
                          {e?.leave && (
                            <span className="text-[12px] font-mono px-1.5 py-px rounded-sm bg-ochre/10 text-ochre leading-none">
                              假
                            </span>
                          )}
                          {!e?.leave && info.isOffDay === true && (
                            <span className="text-[12px] font-mono px-1.5 py-px rounded-sm bg-plum/10 text-plum leading-none">
                              休
                            </span>
                          )}
                          {info.isOffDay === false && (
                            <span className="text-[12px] font-mono px-1.5 py-px rounded-sm bg-navy/10 text-navy leading-none">
                              班
                            </span>
                          )}
                        </div>
                      </div>
                      {info.name && !c.other && (
                        <div className="text-[13px] text-plum mt-1.5 truncate font-mono">
                          {info.name}
                        </div>
                      )}
                      {net != null && !c.other && (
                        <div className="absolute bottom-2.5 left-2.5 right-2.5 font-mono text-[13px] tabular-nums leading-tight flex flex-col items-start gap-0.5">
                          <span className={netColor}>{fmtDuration(shownNet)}</span>
                          {isCounted ? (
                            isRest ? (
                              <span className="text-navy text-[10px] tracking-wide">有效</span>
                            ) : (
                              <span className={ot < 0 ? 'text-plum' : 'text-ochre'}>
                                {ot > 0
                                  ? `+${fmtDuration(ot)}`
                                  : ot < 0
                                    ? `−${fmtDuration(-ot)}`
                                    : '+0'}
                              </span>
                            )
                          ) : (
                            <span className="text-ink-soft text-[10px] tracking-wide">无效</span>
                          )}
                        </div>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
