import { useEffect, useState } from 'react'
import type { ClockLimits, DashboardData, Interval, Period } from '../lib/types'
import { fmtMinutes } from '../lib/format'

type Draft = Omit<Interval, 'interval_id'> & { interval_id?: number }
interface Props {
  data: DashboardData; busy: boolean
  onPeriod: (period: Period) => Promise<void>
  onClockLimits: (limits: ClockLimits) => Promise<void>
  onSave: (interval: Draft) => Promise<void>
  onDelete: (id: number) => Promise<void>
}
const empty: Draft = { name: '', start_time: '12:00', end_time: '13:00', enabled: true }
function IntervalForm({ interval, busy, onSave, onDelete }: {
  interval?: Interval; busy: boolean; onSave: (value: Draft) => Promise<void>; onDelete: (id: number) => Promise<void>
}) {
  const [draft, setDraft] = useState<Draft>(interval || empty)
  const [error, setError] = useState('')
  const id = interval?.interval_id ?? 'new'
  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault(); setError('')
    try { await onSave(draft); if (!interval) setDraft(empty) }
    catch (error) { setError(error instanceof Error ? error.message : String(error)) }
  }
  return <form onSubmit={event => void handleSave(event)} className="border-t border-rule pt-4 mt-4">
    <fieldset disabled={busy} className="workhours-interval-fields grid grid-cols-[1fr_110px_110px_auto_auto] items-end gap-3">
      <label className="workhours-label col-span-1 text-[12px] text-ink-soft">名称
        <input aria-label={`时段名称 ${id}`} required maxLength={100} value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} placeholder={interval ? undefined : '新增非工作时段'} className="block mt-1 p-2 w-full bg-paper border border-rule rounded-sm text-ink" />
      </label>
      <label className="workhours-label text-[12px] text-ink-soft">开始
        <input aria-label={`时段开始 ${id}`} required type="time" value={draft.start_time} onChange={event => setDraft({ ...draft, start_time: event.target.value })} className="block mt-1 p-2 w-full bg-paper border border-rule rounded-sm text-ink" />
      </label>
      <label className="workhours-label text-[12px] text-ink-soft">结束
        <input aria-label={`时段结束 ${id}`} required type="time" value={draft.end_time} onChange={event => setDraft({ ...draft, end_time: event.target.value })} className="block mt-1 p-2 w-full bg-paper border border-rule rounded-sm text-ink" />
      </label>
      <label className="workhours-label flex items-center gap-2 py-2 text-[12px]"><input aria-label={`启用时段 ${id}`} type="checkbox" checked={draft.enabled} onChange={event => setDraft({ ...draft, enabled: event.target.checked })} />启用</label>
      <div className="flex items-center gap-3 justify-end">
        {interval && <button type="button" className="text-[12px] text-plum py-2" aria-label={`删除时段 ${interval.name}`} onClick={() => {
          setError(''); void onDelete(interval.interval_id).catch(error => setError(error instanceof Error ? error.message : String(error)))
        }}>删除</button>}
        <button type="submit" aria-label={interval ? `保存时段 ${interval.name}` : '添加非工作时段'} className="border border-rule rounded-sm px-3 py-2 text-[12px]">{interval ? '保存' : '添加'}</button>
      </div>
    </fieldset>
    {error && <p role="alert" className="text-[13px] text-plum mt-2">{error}</p>}
  </form>
}
function ClockLimitForm({ limits, busy, onSave }: {
  limits: ClockLimits; busy: boolean; onSave: (limits: ClockLimits) => Promise<void>
}) {
  const [start, setStart] = useState(limits.earliest_start_time || '')
  const [end, setEnd] = useState(limits.earliest_end_time || '')
  const [error, setError] = useState('')
  useEffect(() => {
    setStart(limits.earliest_start_time || '')
    setEnd(limits.earliest_end_time || '')
  }, [limits.earliest_start_time, limits.earliest_end_time])
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setError('')
    try { await onSave({ earliest_start_time: start || null, earliest_end_time: end || null }) }
    catch (error) { setError(error instanceof Error ? error.message : String(error)) }
  }
  return <form onSubmit={event => void save(event)} className="border-t border-rule pt-4 mt-4">
    <fieldset disabled={busy} className="flex flex-wrap items-end gap-5">
      <div>
        <label className="workhours-label block text-ink-soft" htmlFor="earliest-start">最早上班打卡时间</label>
        <div className="flex items-center gap-2 mt-2">
          <input id="earliest-start" type="time" step="60" value={start} onChange={event => setStart(event.target.value)} className="p-2 bg-paper border border-rule rounded-sm text-ink" />
          <button type="button" aria-label="清空最早上班打卡时间" disabled={!start || busy} onClick={() => setStart('')} className="text-ink-soft disabled:opacity-40">清空</button>
        </div>
      </div>
      <div>
        <label className="workhours-label block text-ink-soft" htmlFor="earliest-end">最早下班打卡时间</label>
        <div className="flex items-center gap-2 mt-2">
          <input id="earliest-end" type="time" step="60" value={end} onChange={event => setEnd(event.target.value)} className="p-2 bg-paper border border-rule rounded-sm text-ink" />
          <button type="button" aria-label="清空最早下班打卡时间" disabled={!end || busy} onClick={() => setEnd('')} className="text-ink-soft disabled:opacity-40">清空</button>
        </div>
      </div>
      <button type="submit" className="border border-rule rounded-sm px-3 py-2">保存打卡时间限制</button>
    </fieldset>
    <p className="workhours-help text-ink-soft mt-3">留空表示不限制。早到从设定时间开始计工时；预测下班时间不早于设定时间。保存后重新计算已有记录，原始打卡时间保留。</p>
    {error && <p role="alert" className="text-plum text-[13px] mt-2">{error}</p>}
  </form>
}

export default function Settings({ data, busy, onPeriod, onClockLimits, onSave, onDelete }: Props) {
  const [error, setError] = useState('')
  return <details className="mt-8 bg-surface border border-rule rounded-sm p-5">
    <summary className="workhours-section-title cursor-pointer font-mono text-[13px] text-ink-soft tracking-wide">统计周期、打卡限制与非工作时段</summary>
    <div className="mt-5 flex flex-wrap gap-4 items-center justify-between">
      <label className="workhours-label text-[13px]">统计周期
        <select aria-label="统计周期" value={data.settings.period} disabled={busy} className="ml-3 bg-paper border border-rule rounded-sm p-2 text-[13px]" onChange={event => {
          setError(''); void onPeriod(event.target.value as Period).catch(error => setError(error instanceof Error ? error.message : String(error)))
        }}><option value="week">按周</option><option value="month">按月</option></select>
      </label>
      <p className="workhours-help text-[12px] text-ink-soft">每天目标 {fmtMinutes(data.settings.target_minutes_per_day)} · 最低 {fmtMinutes(data.settings.minimum_minutes_per_day)}</p>
    </div>
    {error && <p role="alert" className="text-plum text-[13px] mt-2">{error}</p>}
    <ClockLimitForm limits={data.settings} busy={busy} onSave={onClockLimits} />
    <p className="workhours-help text-[12px] text-ink-soft mt-4">启用的时段从打卡时长中扣除；修改后会重新计算已有记录。</p>
    {data.intervals.map(interval => <IntervalForm key={JSON.stringify(interval)} interval={interval} busy={busy} onSave={onSave} onDelete={onDelete} />)}
    <IntervalForm busy={busy} onSave={onSave} onDelete={onDelete} />
  </details>
}
