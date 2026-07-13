import { useEffect, useState } from 'react'
import type { WorkEntry } from '../lib/types'
import { calcNet, DAILY_TARGET, fmtDuration, floorTo30Min } from '../lib/workHours'
import TimePicker from './TimePicker'

interface Props {
  date: string
  entry?: WorkEntry
  isRestDay: boolean
  externalBusy?: boolean
  onClose: () => void
  onSave: (e: WorkEntry) => Promise<void>
  onDelete: () => Promise<void>
}

export default function EntryModal({
  date,
  entry,
  isRestDay,
  externalBusy = false,
  onClose,
  onSave,
  onDelete,
}: Props) {
  const [i, setI] = useState(entry?.in ?? '')
  const [o, setO] = useState(entry?.out ?? '')
  const [counts, setCounts] = useState<boolean>(entry?.counts ?? !isRestDay)
  const [busyAction, setBusyAction] = useState<'save' | 'delete' | null>(null)
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && busyAction === null && !externalBusy) onClose()
    }
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [busyAction, externalBusy, onClose])

  const net = calcNet(i, o)
  const bothFilled = !!(i && o)
  const oneFilled = !!i !== !!o
  const valid = bothFilled && net != null
  const err =
    bothFilled && net == null
      ? '下班时间需晚于上班时间（跨天打卡不支持）'
      : oneFilled
        ? '请同时填写上、下班时间，或都留空'
        : ''
  const ot = net != null ? net - DAILY_TARGET : 0
  const displayNet = isRestDay ? floorTo30Min(net!) : net!

  const runAction = async (kind: 'save' | 'delete', action: () => Promise<void>) => {
    setBusyAction(kind)
    setActionError('')
    try {
      await action()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error))
    } finally {
      setBusyAction(null)
    }
  }

  const handleSave = () => {
    if (!valid || busyAction !== null || externalBusy) return
    void runAction('save', () => onSave({ in: i, out: o, counts }))
  }

  const handleDelete = () => {
    if (busyAction !== null || externalBusy) return
    void runAction('delete', onDelete)
  }

  return (
    <div
      className="fixed inset-0 bg-ink/30 flex items-center justify-center z-20 px-4"
      onClick={() => {
        if (busyAction === null && !externalBusy) onClose()
      }}
    >
      <div
        className="bg-paper border border-rule rounded-sm p-8 w-[380px] shadow-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-baseline justify-between mb-7">
          <h3 className="font-display text-[26px] text-ink tracking-tight">{date}</h3>
          <span className="text-[13px] uppercase tracking-[0.2em] text-ink-soft font-mono">
            Entry
          </span>
        </div>

        <label className="block text-[13px] uppercase tracking-[0.16em] text-ink-soft font-mono mb-2">
          上班 · In
        </label>
        <TimePicker value={i} onChange={setI} ariaLabel="上班 · In" />

        <label className="block text-[13px] uppercase tracking-[0.16em] text-ink-soft font-mono mb-2 mt-6">
          下班 · Out
        </label>
        <TimePicker value={o} onChange={setO} ariaLabel="下班 · Out" />

        {isRestDay && (
          <div className="mt-5 flex items-center gap-3 select-none">
            <button
              type="button"
              role="checkbox"
              aria-checked={counts}
              onClick={() => setCounts((c) => !c)}
              className={`w-5 h-5 rounded-sm border flex items-center justify-center transition-colors ${
                counts ? 'bg-navy border-navy' : 'bg-paper border-rule'
              }`}
            >
              {counts && (
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 12 12"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-paper"
                  aria-hidden
                >
                  <path d="M2 6.5 L5 9 L10 3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
            <span className="text-[13px] text-ink">计入工时</span>
            <span className="text-[12px] text-ink-soft">开启后，该日算入总时长与盈余</span>
          </div>
        )}

        {(err || actionError) && (
          <div className="text-plum text-[13px] mt-3 font-mono">{err || actionError}</div>
        )}

        <div className="mt-6 pt-5 border-t border-rule min-h-[56px]">
          {net != null ? (
            <div className="flex items-baseline gap-3 font-mono tabular-nums flex-wrap">
              <span className="text-[13px] uppercase tracking-[0.16em] text-ink-soft">Net</span>
              <span className="font-display text-[32px] text-ink leading-none">
                {fmtDuration(displayNet)}
              </span>
              {!isRestDay && ot > 0 && <span className="text-ochre text-sm">+{fmtDuration(ot)} 加班</span>}
              {!isRestDay && ot < 0 && <span className="text-ink-soft text-sm">差 {fmtDuration(-ot)}</span>}
            </div>
          ) : (
            <div className="text-ink-soft text-[13px] font-mono">—</div>
          )}
        </div>

        <div className="flex justify-between items-center mt-7 gap-2">
          {entry ? (
            <button
              onClick={handleDelete}
              disabled={busyAction !== null || externalBusy}
              className="text-[13px] uppercase tracking-[0.16em] font-mono text-plum hover:underline"
            >
              {busyAction === 'delete' ? '删除中…' : '删除'}
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2 ml-auto">
            <button
              onClick={onClose}
              disabled={busyAction !== null || externalBusy}
              className="px-5 py-2.5 text-[13px] text-ink-soft hover:text-ink font-mono uppercase tracking-[0.14em] transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={!valid || busyAction !== null || externalBusy}
              className="px-6 py-2.5 bg-ink text-paper text-[13px] font-mono uppercase tracking-[0.14em] rounded-sm disabled:opacity-30 hover:bg-ink-soft transition-colors"
            >
              {busyAction === 'save' ? '保存中…' : '保存'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
