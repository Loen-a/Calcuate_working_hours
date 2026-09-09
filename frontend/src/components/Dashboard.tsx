import type { DashboardData } from '../lib/types'
import { fmtMinutes, signedMinutes } from '../lib/format'
import { useCountUp } from '../lib/useCountUp'

function Card({ label, value, sub, tone = 'ink' }: {
  label: string; value: string; sub: string; tone?: 'ink' | 'navy' | 'plum'
}) {
  return (
    <div className="bg-surface border border-rule rounded-sm p-5 min-w-0">
      <div className="workhours-label text-[13px] tracking-[0.16em] text-ink-soft font-mono mb-2.5">{label}</div>
      <div className={`workhours-stat-value font-mono tabular-nums leading-tight text-[24px] ${tone === 'navy' ? 'text-navy' : tone === 'plum' ? 'text-plum' : 'text-ink'}`}>{value}</div>
      <div className="workhours-help text-[12px] text-ink-soft mt-2.5 font-mono tabular-nums">{sub}</div>
    </div>
  )
}
export default function Dashboard({ data }: { data: DashboardData }) {
  const { month } = data
  const balance = useCountUp(month.balance_minutes)
  return (
    <section className="workhours-summary" aria-label="工时统计">
      <div className="workhours-summary-grid grid grid-cols-4 gap-3">
        <Card label="当月目标" value={fmtMinutes(month.target_minutes)} sub={`${month.workday_count} 工作日 · 已排除全天请假`} />
        <Card label="已完成" value={fmtMinutes(month.completed_minutes)} sub={`已录入 ${month.recorded_days} 天`} />
        <Card label={month.balance_minutes >= 0 ? '盈余' : '缺口'} value={signedMinutes(balance)} tone={month.balance_minutes >= 0 ? 'navy' : 'plum'} sub="当月累计工时余额" />
        <Card label="工作日" value={`${month.recorded_days}/${month.workday_count}`} sub="已录入 / 本月工作日" />
      </div>
    </section>
  )
}
