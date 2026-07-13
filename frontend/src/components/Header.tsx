import { useRef } from 'react'
import type { Theme } from '../lib/types'

interface Props {
  y: number
  m: number
  theme: Theme
  themeBusy: boolean
  importBusy: boolean
  onPrev: () => void
  onNext: () => void
  onToday: () => void
  onThemeToggle: () => void
  onExport: () => void
  onImport: (file: File) => void
}

export default function Header({
  y,
  m,
  theme,
  themeBusy,
  importBusy,
  onPrev,
  onNext,
  onToday,
  onThemeToggle,
  onExport,
  onImport,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  return (
    <header className="border-b border-rule">
      <div className="max-w-5xl mx-auto px-8 py-6 flex items-center justify-between">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-[26px] font-medium tracking-tight text-ink">工时</span>
          <span className="text-[13px] uppercase tracking-[0.2em] text-ink-soft font-mono">Workhours</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onPrev}
            disabled={importBusy}
            className="w-11 h-11 grid place-items-center rounded-full text-ink-soft hover:text-ink hover:bg-surface transition-colors text-xl leading-none"
            aria-label="上一月"
          >
            ‹
          </button>
          <span className="font-display text-[19px] tabular-nums mx-3 min-w-[100px] text-center text-ink">
            {y} · {String(m).padStart(2, '0')}
          </span>
          <button
            onClick={onNext}
            disabled={importBusy}
            className="w-11 h-11 grid place-items-center rounded-full text-ink-soft hover:text-ink hover:bg-surface transition-colors text-xl leading-none"
            aria-label="下一月"
          >
            ›
          </button>
          <button
            onClick={onToday}
            disabled={importBusy}
            className="ml-3 px-4 py-2.5 text-[13px] uppercase tracking-[0.14em] text-ink-soft hover:text-ink font-mono border border-rule rounded-full hover:border-ink-soft transition-colors"
          >
            今天
          </button>
          <button
            onClick={onExport}
            className="ml-3 px-4 py-2.5 text-[13px] uppercase tracking-[0.14em] text-ink-soft hover:text-ink font-mono border border-rule rounded-full hover:border-ink-soft transition-colors"
            title="导出所有打卡为 JSON（建议先在浏览器把下载位置指向项目下的 data/）"
          >
            导出
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={themeBusy}
            className="px-4 py-2.5 text-[13px] uppercase tracking-[0.14em] text-ink-soft hover:text-ink font-mono border border-rule rounded-full hover:border-ink-soft transition-colors"
          >
            {importBusy ? '导入中…' : '导入'}
          </button>
          <button
            onClick={onThemeToggle}
            disabled={themeBusy}
            className="px-4 py-2.5 text-[13px] uppercase tracking-[0.14em] text-ink-soft hover:text-ink font-mono border border-rule rounded-full hover:border-ink-soft transition-colors"
            title="切换主题（青绿 / 冷色）"
          >
            {theme === 'teal' ? '青绿' : '冷色'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            disabled={themeBusy}
            accept=".json,application/json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) onImport(f)
              e.target.value = ''
            }}
          />
        </div>
      </div>
    </header>
  )
}
