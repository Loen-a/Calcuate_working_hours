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
import type { Day } from '../lib/types'
import { fmtMinutes } from '../lib/format'

interface Props { days: Day[] }

interface Point {
  day: number
  balance: number
}

const NAVY = 'var(--chart-positive, #2A4A6B)'
const PLUM = 'var(--chart-negative, #7A3A4E)'
const SOFT = 'var(--chart-muted, #5E646C)'
const RULE = 'var(--chart-rule, #C5CACE)'

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
    <div className="workhours-chart-tooltip bg-paper border border-rule px-3.5 py-2.5 font-mono text-[14px] tabular-nums shadow-sm">
      <div className="text-ink-soft">{label} 日</div>
      <div className={v >= 0 ? 'text-navy' : 'text-plum'}>
        {sign}
        {fmtMinutes(Math.abs(v))}
      </div>
    </div>
  )
}

export default function TrendChart({ days }: Props) {
  const data: Point[] = days
    .filter(day => day.cumulative_balance_minutes != null)
    .map(day => ({ day: Number(day.date.slice(8)), balance: day.cumulative_balance_minutes! }))

  if (data.length === 0) return null
  const last = data[data.length - 1].balance
  const stroke = last >= 0 ? NAVY : PLUM
  const grad = last >= 0 ? 'g-navy' : 'g-plum'

  return (
    <section className="workhours-trend" aria-label="工时趋势">
      <div className="flex items-center gap-3 mb-5">
        <span className="workhours-section-title text-[13px] tracking-[0.2em] text-ink-soft font-mono">
          累计盈余 / 缺口
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
              tickFormatter={(v: number) => (v < 0 ? '−' : '') + fmtMinutes(Math.abs(v))}
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
