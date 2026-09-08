import { useEffect, useRef, useState } from 'react'
import type { CalendarKind, Day, Entry, Preview } from '../lib/types'
import { getPreview } from '../lib/api'
import { fmtMinutes } from '../lib/format'
import TimePicker from './TimePicker'

interface Props {
  day: Day; preview: Preview; externalBusy: boolean
  onClose: () => void; onSave: (entry: Entry) => Promise<void>; onDelete: () => Promise<void>
  onLeave: (enabled: boolean) => Promise<void>; onCalendar: (kind: CalendarKind | null) => Promise<void>
}
export default function EntryModal({ day, preview, externalBusy, onClose, onSave, onDelete, onLeave, onCalendar }: Props) {
  const [start, setStart] = useState(day.entry?.start_time || '')
  const [end, setEnd] = useState(day.entry?.end_time || '')
  const [calendar, setCalendar] = useState<CalendarKind | ''>(day.manual_override || '')
  const [livePreview, setLivePreview] = useState<Preview>(preview)
  const [previewError, setPreviewError] = useState('')
  const [previewBusy, setPreviewBusy] = useState(false)
  const [action, setAction] = useState<string | null>(null)
  const [error, setError] = useState('')
  const dialogRef = useRef<HTMLDivElement>(null)
  const busy = externalBusy || action !== null

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    dialogRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow; previous?.focus() }
  }, [])
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onClose()
      if (event.key === 'Tab') {
        const elements = dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), [href]')
        if (!elements?.length) return
        const first = elements[0], last = elements[elements.length - 1]
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [busy, onClose])
  useEffect(() => {
    setPreviewError('')
    if (start === (day.entry?.start_time || '')) { setLivePreview(preview); setPreviewBusy(false); return }
    if (!start || day.leave) { setLivePreview({ available: false }); setPreviewBusy(false); return }
    const controller = new AbortController()
    setPreviewBusy(true)
    const timer = window.setTimeout(() => {
      getPreview(day.date, start, controller.signal)
        .then(value => { if (!controller.signal.aborted) setLivePreview(value) })
        .catch(error => { if (!controller.signal.aborted) setPreviewError(error instanceof Error ? error.message : String(error)) })
        .finally(() => { if (!controller.signal.aborted) setPreviewBusy(false) })
    }, 200)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [start, day.date, day.leave, day.entry?.start_time, preview])

  const run = async (kind: string, callback: () => Promise<void>) => {
    if (busy) return
    setAction(kind); setError('')
    try { await callback(); onClose() }
    catch (error) { setError(error instanceof Error ? error.message : String(error)) }
    finally { setAction(null) }
  }
  return (
    <div className="fixed inset-0 bg-ink/30 flex items-center justify-center z-20 px-3 py-4" onClick={() => { if (!busy) onClose() }}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="entry-title" tabIndex={-1} className="workhours-entry-modal bg-paper border border-rule rounded-sm p-5 sm:p-8 w-full max-w-[440px] max-h-[92dvh] overflow-y-auto shadow-sm outline-none" onClick={event => event.stopPropagation()}>
        <div className="flex items-baseline justify-between mb-5 gap-3">
          <h3 id="entry-title" className="workhours-section-title font-display text-[26px] tracking-tight">{day.date}</h3>
          <span className="workhours-meta text-[12px] tracking-[0.2em] text-ink-soft font-mono">Entry</span>
        </div>
        <p className="workhours-help text-[13px] text-ink-soft mb-4">{day.calendar_name}{day.leave ? ' · 当天不计入工时和目标，打卡记录保留' : ''}</p>
        <fieldset disabled={busy}>
          <label className="workhours-label block text-[13px] tracking-[0.16em] text-ink-soft font-mono mb-2">上班 · In</label>
          <TimePicker value={start} onChange={setStart} ariaLabel="上班 · In" />
          <label className="workhours-label block text-[13px] tracking-[0.16em] text-ink-soft font-mono mb-2 mt-5">下班 · Out</label>
          <TimePicker value={end} onChange={setEnd} ariaLabel="下班 · Out" />
        </fieldset>
        <p className="workhours-help text-[12px] text-ink-soft mt-3 leading-relaxed">可以仅填写上班时间；下班早于上班时按次日处理。</p>
        <div className="workhours-entry-preview mt-4 pt-4 border-t border-rule text-[13px] font-mono leading-relaxed" aria-live="polite">
          {previewBusy ? '正在计算最早下班时间…' : previewError ? <span className="text-plum">预测读取失败：{previewError}</span>
            : day.leave ? '全天请假，无下班预测'
              : livePreview.available ? <><span className="text-ink-soft">最早下班 </span><strong>{livePreview.suggested_end_label || livePreview.suggested_end}</strong><p className="text-ink-soft">需完成 {livePreview.required_label || fmtMinutes(livePreview.required_minutes || 0)} · {livePreview.reason_label}</p></>
                : livePreview.reason_label || '填写上班时间后查看预测'}
          {day.actual_minutes != null && <p className="text-ink-soft mt-1">已保存记录的净工时：{fmtMinutes(day.actual_minutes)}</p>}
        </div>
        {error && <p role="alert" className="text-plum text-[13px] mt-3">{error}</p>}
        <div className="flex justify-between items-center gap-2 mt-5">
          {day.entry ? <button disabled={busy} className="text-[13px] text-plum hover:underline disabled:opacity-40" onClick={() => void run('delete', onDelete)}>{action === 'delete' ? '删除中…' : '删除打卡'}</button> : <span />}
          <div className="flex gap-2 ml-auto">
            <button disabled={busy} className="px-3 py-2.5 text-[13px] text-ink-soft disabled:opacity-40" onClick={onClose}>取消</button>
            <button disabled={busy || (!start && !end)} className="workhours-primary-action px-4 py-2.5 bg-ink text-paper text-[13px] rounded-sm disabled:opacity-30" onClick={() => void run('save', () => onSave({ start_time: start || null, end_time: end || null }))}>{action === 'save' ? '保存中…' : '保存打卡'}</button>
          </div>
        </div>
        <div className="mt-6 pt-5 border-t border-rule">
          <div className="flex items-center justify-between gap-3">
            <div><p className="workhours-label text-[13px]">全天请假</p><p className="workhours-help text-[12px] text-ink-soft mt-1">独立保存，保留打卡与日历标记</p></div>
            <button disabled={busy} onClick={() => void run('leave', () => onLeave(!day.leave))} className="px-3 py-2.5 border border-ochre/40 text-ochre text-[12px] rounded-sm disabled:opacity-40">{action === 'leave' ? '保存中…' : day.leave ? '取消全天请假' : '设为全天请假'}</button>
          </div>
          <div className="flex items-end gap-2 mt-5">
            <label className="workhours-label flex-1 min-w-0 text-[13px] text-ink-soft">手动日历标记
              <select aria-label="手动日历标记" disabled={busy} value={calendar} onChange={event => setCalendar(event.target.value as CalendarKind | '')} className="mt-2 block w-full bg-surface border border-rule rounded-sm p-2 text-ink">
                <option value="">自动日历</option><option value="holiday">休息日</option><option value="workday">工作日</option>
              </select>
            </label>
            <button disabled={busy || calendar === (day.manual_override || '')} className="px-3 py-2 border border-rule rounded-sm text-[12px] disabled:opacity-40" onClick={() => void run('calendar', () => onCalendar(calendar || null))}>应用日历</button>
          </div>
        </div>
      </div>
    </div>
  )
}
