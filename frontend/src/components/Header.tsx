import { useRef } from 'react'
import type { Theme } from '../lib/types'

interface Props {
  date: string; theme: Theme; busy: boolean; importBusy: boolean
  onPrev: () => void; onNext: () => void; onToday: () => void
  onThemeToggle: () => void; onExport: () => void; onImport: (file: File) => void
}
const buttonClass = 'px-3 py-2.5 text-[12px] text-ink-soft hover:text-ink font-mono border border-rule rounded-full hover:border-ink-soft transition-colors disabled:opacity-40'
export default function Header(props: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [y, m] = props.date.split('-')
  return (
    <header className="border-b border-rule">
      <div className="max-w-5xl mx-auto px-4 sm:px-8 py-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-[26px] font-medium tracking-tight">工时</span>
          <span className="text-[13px] uppercase tracking-[0.2em] text-ink-soft font-mono">Workhours</span>
        </div>
        <nav className="flex items-center gap-1" aria-label="月份导航">
          <button onClick={props.onPrev} disabled={props.busy} className="w-9 h-10 text-xl hover:bg-surface rounded-full disabled:opacity-40" aria-label="上一月">‹</button>
          <span className="font-display text-[19px] tabular-nums mx-2 min-w-[100px] text-center">{y} · {m}</span>
          <button onClick={props.onNext} disabled={props.busy} className="w-9 h-10 text-xl hover:bg-surface rounded-full disabled:opacity-40" aria-label="下一月">›</button>
          <button onClick={props.onToday} disabled={props.busy} className={buttonClass}>今天</button>
        </nav>
        <div className="flex items-center justify-end flex-wrap gap-2 w-full">
          <button onClick={props.onExport} disabled={props.busy} className={buttonClass} title="导出打卡、设置、请假和日历的完整 JSON 备份">导出</button>
          <button onClick={() => fileInputRef.current?.click()} disabled={props.busy} className={buttonClass}>{props.importBusy ? '导入中…' : '导入'}</button>
          <button onClick={props.onThemeToggle} disabled={props.busy} className={buttonClass} title="切换主题（青绿 / 冷色）">{props.theme === 'teal' ? '青绿' : '冷色'}</button>
          <a href={'/interface/old?reference_date=' + encodeURIComponent(props.date)} className={buttonClass} aria-disabled={props.busy} onClick={event => { if (props.busy) event.preventDefault() }}>切换旧界面</a>
          <input ref={fileInputRef} type="file" aria-label="选择 JSON 备份" disabled={props.busy} accept=".json,application/json" className="hidden" onChange={event => {
            const file = event.target.files?.[0]
            if (file) props.onImport(file)
            event.target.value = ''
          }} />
        </div>
      </div>
    </header>
  )
}
