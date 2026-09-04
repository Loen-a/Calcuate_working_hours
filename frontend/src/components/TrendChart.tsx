import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Entries, HolidayMap } from '../lib/types'
import { calcNet, DAILY_TARGET, fmtDate, fmtDuration, floorTo30Min, isEntryCounted } from '../lib/workHours'
import { dayInfo } from '../lib/holidays'

interface Props {
  y: number
  m: number
  entries: Entries
  hMap?: HolidayMap
}

interface Point {
  day: number
  balance: number
}

const NAVY = '#2A4A6B'
const PLUM = '#7A3A4E'
const SOFT = '#5E646C'
const RULE = '#C5CACE'

interface TipProps {
  active?: boolean
  payload?: Array<{ value: number }>
  label?: number
}
function Tip({ active, payload, label }: TipProps) {
  if (!active || !payload?.length) return null
  const v = payload[0].value
  const sign = v > 0 ? '+' : v < 0 ? '−' : ''
  return (
    <div className="bg-paper border border-rule px-3.5 py-2.5 font-mono text-[14px] tabular-nums shadow-sm">
      <div className="text-ink-soft">{label} 日</div>
      <div className={v >= 0 ? 'text-navy' : 'text-plum'}>
        {sign}
        {fmtDuration(Math.abs(v))}
      </div>
    </div>
  )
}

export default function TrendChart({ y, m, entries, hMap }: Props) {
  const data = useMemo<Point[]>(() => {
    const days = new Date(y, m, 0).getDate()
    const today = new Date()
    const isCurMonth = today.getFullYear() === y && today.getMonth() + 1 === m
    let maxEntryDay = 0
    for (let d = 1; d <= days; d++) if (entries[fmtDate(y, m, d)]) maxEntryDay = d
    const endDay = Math.max(maxEntryDay, isCurMonth ? today.getDate() : 0)
    if (endDay === 0) return []
    const pts: Point[] = []
    let bal = 0
    for (let d = 1; d <= endDay; d++) {
      const e = entries[fmtDate(y, m, d)]
      if (e?.leave) { pts.push({ day: d, balance: +bal.toFixed(2) }); continue }
      if (e) {
        const info = dayInfo(y, m, d, hMap)
        const isWorkday = info.type === 'work'
        const counted = isEntryCounted(e.counts, isWorkday)
        if (counted) {
          const net = calcNet(e.in, e.out)
          if (net != null) {
            const effective = isWorkday ? net : floorTo30Min(net) // 补时长按半小时向下取整
            bal += isWorkday ? effective - DAILY_TARGET : effective
          }
        }
      }
      pts.push({ day: d, balance: +bal.toFixed(2) })
    }
    return pts
  }, [y, m, entries, hMap])

  if (data.length === 0) return null
  const last = data[data.length - 1].balance
  const stroke = last >= 0 ? NAVY : PLUM
  const grad = last >= 0 ? 'g-navy' : 'g-plum'

  return (
    <section>
      <div className="flex items-center gap-3 mb-5">
        <span className="text-[13px] uppercase tracking-[0.2em] text-ink-soft font-mono">Trend</span>
        <span className="text-ink-soft/40 font-mono">·</span>
        <span className="text-[13px] tracking-[0.2em] text-ink-soft font-mono">
          累计盈余 / 缺口 (相对 9h)
        </span>
      </div>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="g-navy" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={NAVY} stopOpacity={0.28} />
                <stop offset="100%" stopColor={NAVY} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="g-plum" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={PLUM} stopOpacity={0.28} />
                <stop offset="100%" stopColor={PLUM} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={RULE} strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="day"
              tick={{ fontSize: 13, fill: SOFT, fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              axisLine={{ stroke: RULE }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 13, fill: SOFT, fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              axisLine={false}
              width={88}
              tickFormatter={(v: number) => (v < 0 ? '−' : '') + fmtDuration(Math.abs(v))}
            />
            <ReferenceLine y={0} stroke={SOFT} strokeOpacity={0.5} />
            <Tooltip content={<Tip />} cursor={{ stroke: SOFT, strokeOpacity: 0.4 }} />
            <Area
              type="monotone"
              dataKey="balance"
              stroke={stroke}
              strokeWidth={1.5}
              fill={`url(#${grad})`}
              isAnimationActive={true}
              animationDuration={700}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
