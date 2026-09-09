import type { Day, Preview } from '../lib/types'
import { fmtMinutes, signedMinutes } from '../lib/format'

interface Props {
  day: Day
  preview: Preview
  today: string
  busy: boolean
  onEdit: () => void
}

export default function SelectedDayPanel({ day, preview, today, busy, onEdit }: Props) {
  const status = day.leave ? '全天请假' : day.is_workday ? '工作日' : '休息日'
  const counted = day.is_workday && !day.leave
  const endLabel = preview.suggested_end_label || preview.suggested_end
  const canPredict = counted && Boolean(day.entry?.start_time) && preview.available && Boolean(endLabel)
  const required = preview.required_minutes ?? day.required_minutes
  const balance = preview.balance_before_minutes ?? day.balance_before_minutes
  const actualLabel = day.actual_minutes != null
    ? fmtMinutes(day.actual_minutes)
    : !counted ? '不计入' : day.entry ? '待补全' : '尚未记录'

  let predictionMessage: string
  if (day.leave) {
    predictionMessage = '全天请假，无下班预测；当天不计入工时与目标，原打卡记录保留。'
  } else if (!day.is_workday) {
    predictionMessage = '休息日不计入工时与目标，无需下班预测。'
  } else if (!day.entry?.start_time) {
    predictionMessage = '尚未记录上班时间，填写后查看预测。'
  } else {
    predictionMessage = preview.reason_label || (canPredict ? '' : '当前日期暂无下班预测。')
  }

  return (
    <aside className="workhours-day-panel" aria-label="所选日期详情">
      <header className="workhours-day-heading">
        <div>
          <p className="workhours-day-label">所选日期</p>
          <h2>{day.date}</h2>
        </div>
        {day.date === today && <span className="workhours-day-today">今天</span>}
      </header>
      <div className="workhours-day-status">
        <span>{status}</span>
        {day.calendar_name !== status && <span className="workhours-day-calendar-name">{day.calendar_name}</span>}
      </div>

      <dl className="workhours-day-punches">
        <div><dt>上班</dt><dd>{day.entry?.start_time || '--:--'}</dd></div>
        <div><dt>下班</dt><dd>{day.entry?.end_time || '--:--'}</dd></div>
      </dl>

      <section className="workhours-day-prediction" aria-label="最早下班预测">
        <h3>最早下班</h3>
        {canPredict && <p className="workhours-day-prediction-time">{endLabel}</p>}
        {predictionMessage && <p className="workhours-day-prediction-note">{predictionMessage}</p>}
      </section>

      <dl className="workhours-day-facts">
        <div><dt>净工时</dt><dd>{actualLabel}</dd></div>
        {counted && <>
          <div><dt>需工作</dt><dd>{preview.required_label || (required != null ? fmtMinutes(required) : '—')}</dd></div>
          <div><dt>带入余额</dt><dd>{preview.balance_label || signedMinutes(balance)}</dd></div>
        </>}
      </dl>
      <button type="button" className="workhours-day-edit workhours-primary-action" disabled={busy} onClick={onEdit}>
        编辑所选日期
      </button>
    </aside>
  )
}
