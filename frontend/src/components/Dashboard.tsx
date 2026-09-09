import type { DashboardData } from '../lib/types'
import { fmtMinutes, signedMinutes } from '../lib/format'
import { useCountUp } from '../lib/useCountUp'

function Card({ label, value, sub, tone = 'ink' }: {
  label: string; value: string; sub: string; tone?: 'ink' | 'navy' | 'plum'
}) {
  return (
    <div className="bg-surface border border-rule rounded-sm p-4 sm:p-5 min-w-0">
      <div className="workhours-label text-[13px] tracking-[0.16em] text-ink-soft font-mono mb-2.5">{label}</div>
      <div className={`workhours-stat-value font-mono tabular-nums leading-tight text-[22px] sm:text-[24px] ${tone === 'navy' ? 'text-navy' : tone === 'plum' ? 'text-plum' : 'text-ink'}`}>{value}</div>
      <div className="workhours-help text-[12px] text-ink-soft mt-2.5 font-mono tabular-nums">{sub}</div>
    </div>
  )
}
export default function Dashboard({ data }: { data: DashboardData }) {
  const { month, selected_preview: preview, selected_date: date } = data
  const day = data.days.find(item => item.date === date)
  const balance = useCountUp(month.balance_minutes)
  return (
    <section aria-label="工时统计">
      <div className="workhours-forecast-card bg-surface border border-rule rounded-sm p-5 mb-3">
        <div className="flex items-center justify-between mb-3 gap-3">
          <span className="workhours-section-title text-[13px] tracking-[0.16em] text-ink-soft font-mono">最早下班预测</span>
          <span className="workhours-meta text-[12px] text-ink-soft font-mono">{date}{date === data.today ? ' · 今天' : ''}</span>
        </div>
        <div className="workhours-forecast-time flex items-baseline flex-wrap gap-3 font-display font-medium tabular-nums leading-none text-[36px] sm:text-[44px]">
          <span>{day?.entry?.start_time || '--:--'}</span>
          <span className="workhours-forecast-arrow text-ink-soft text-[24px]">→</span>
          <span className={preview.available ? 'text-ink' : 'text-ink-soft'}>
            {preview.available ? (preview.suggested_end_label || preview.suggested_end || '--:--') : '--:--'}
          </span>
        </div>
        <p className="workhours-help text-[12px] text-ink-soft mt-3 font-mono leading-relaxed">
          {preview.available
            ? `需完成 ${preview.required_label || fmtMinutes(preview.required_minutes || 0)} · ${preview.reason_label || ''}`
            : day?.leave ? '全天请假 · 已有打卡保留，当天不计入工时和目标' : preview.reason_label || '请选择工作日期并填写上班时间，查看下班预测'}
        </p>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card label="当月目标" value={fmtMinutes(month.target_minutes)} sub={`${month.workday_count} 工作日 · 已排除全天请假`} />
        <Card label="已完成" value={fmtMinutes(month.completed_minutes)} sub={`已录入 ${month.recorded_days} 天`} />
        <Card label={month.balance_minutes >= 0 ? '盈余' : '缺口'} value={signedMinutes(balance)} tone={month.balance_minutes >= 0 ? 'navy' : 'plum'} sub="当月累计工时余额" />
        <Card label="工作日" value={`${month.recorded_days}/${month.workday_count}`} sub="已录入 / 本月工作日" />
      </div>
    </section>
  )
}
