import { forwardRef, useEffect, useRef, useState } from 'react'

interface Props {
  value: string // "HH:MM" or ""
  onChange: (v: string) => void
  ariaLabel: string
}

const HOURS = Array.from({ length: 24 }, (_, i) => i)
const MINUTES = Array.from({ length: 60 }, (_, i) => i)
const pad = (n: number) => String(n).padStart(2, '0')

function parseVal(v: string) {
  if (!v || !/^\d{1,2}:\d{2}$/.test(v)) return null
  const [h, m] = v.split(':').map(Number)
  if (h < 0 || h > 23 || m < 0 || m > 59) return null
  return { h, m }
}

interface ColumnProps {
  items: number[]
  selected: number
  onSelect: (n: number) => void
  label: string
}

const Column = forwardRef<HTMLDivElement, ColumnProps>(function Column(
  { items, selected, onSelect, label },
  ref,
) {
  return (
    <div className="flex-1 min-w-0">
      <div className="workhours-label text-[11px] uppercase tracking-[0.14em] text-ink-soft font-mono text-center mb-1.5">
        {label}
      </div>
      <div
        ref={ref}
        style={{
          maskImage:
            'linear-gradient(to bottom, transparent, black 12%, black 88%, transparent)',
          WebkitMaskImage:
            'linear-gradient(to bottom, transparent, black 12%, black 88%, transparent)',
        }}
        className="time-col max-h-[150px] overflow-y-auto"
      >
        {items.map((n) => {
          const isSel = n === selected
          return (
            <button
              key={n}
              type="button"
              data-sel={isSel}
              onClick={(e) => {
                onSelect(n)
                e.currentTarget.scrollIntoView({ block: 'center' })
              }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowUp') {
                  e.preventDefault()
                  onSelect((n - 1 + items.length) % items.length)
                } else if (e.key === 'ArrowDown') {
                  e.preventDefault()
                  onSelect((n + 1) % items.length)
                }
              }}
              className={`workhours-time-option w-full h-9 grid place-items-center font-mono text-[15px] tabular-nums rounded-sm transition-colors ${
                isSel
                  ? 'bg-navy text-paper'
                  : 'text-ink-soft hover:bg-rule/50 hover:text-ink'
              }`}
            >
              {pad(n)}
            </button>
          )
        })}
      </div>
    </div>
  )
})

export default function TimePicker({ value, onChange, ariaLabel }: Props) {
  const [open, setOpen] = useState(false)
  const cur = parseVal(value)
  const [h, setH] = useState<number>(cur?.h ?? 9)
  const [m, setM] = useState<number>(cur?.m ?? 0)
  const wrapRef = useRef<HTMLDivElement>(null)
  const hColRef = useRef<HTMLDivElement>(null)
  const mColRef = useRef<HTMLDivElement>(null)
  const hRef = useRef(h)
  const mRef = useRef(m)
  const wasOpen = useRef(false)

  // 把最新 h/m 同步到 ref，供原生 wheel 处理器读取（避免闭包过期）
  hRef.current = h
  mRef.current = m

  // 仅在"关闭→打开"那一瞬从 value 同步；打开期间 value 变化（live commit）不重置
  useEffect(() => {
    if (open && !wasOpen.current) {
      const c = parseVal(value)
      setH(c?.h ?? 9)
      setM(c?.m ?? 0)
    }
    wasOpen.current = open
  }, [open, value])

  // 点外部关闭
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  // 打开时把选中项滚到中间
  useEffect(() => {
    if (!open) return
    const t = window.setTimeout(() => {
      hColRef.current
        ?.querySelector<HTMLElement>('[data-sel="true"]')
        ?.scrollIntoView({ block: 'center' })
      mColRef.current
        ?.querySelector<HTMLElement>('[data-sel="true"]')
        ?.scrollIntoView({ block: 'center' })
    }, 0)
    return () => window.clearTimeout(t)
  }, [open])

  // 滚轮：原生非 passive 监听，preventDefault 真正生效，页面与列都不会被原生滚动
  useEffect(() => {
    if (!open) return
    const hEl = hColRef.current
    const mEl = mColRef.current
    if (!hEl || !mEl) return
    const handle = (which: 'h' | 'm', e: WheelEvent) => {
      e.preventDefault()
      const el = which === 'h' ? hEl : mEl
      if (which === 'h') {
        const nh = (hRef.current + (e.deltaY > 0 ? 1 : -1) + 24) % 24
        setH(nh)
        onChange(`${pad(nh)}:${pad(mRef.current)}`)
      } else {
        const nm = (mRef.current + (e.deltaY > 0 ? 1 : -1) + 60) % 60
        setM(nm)
        onChange(`${pad(hRef.current)}:${pad(nm)}`)
      }
      requestAnimationFrame(() => {
        el.querySelector<HTMLElement>('[data-sel="true"]')?.scrollIntoView({ block: 'center' })
      })
    }
    const hHandler = (e: WheelEvent) => handle('h', e)
    const mHandler = (e: WheelEvent) => handle('m', e)
    hEl.addEventListener('wheel', hHandler, { passive: false })
    mEl.addEventListener('wheel', mHandler, { passive: false })
    return () => {
      hEl.removeEventListener('wheel', hHandler)
      mEl.removeEventListener('wheel', mHandler)
    }
  }, [open, onChange])

  // live commit：选哪一项字段立刻更新
  const pickH = (nh: number) => {
    setH(nh)
    onChange(`${pad(nh)}:${pad(m)}`)
  }
  const pickM = (nm: number) => {
    setM(nm)
    onChange(`${pad(h)}:${pad(nm)}`)
  }
  const setNow = () => {
    const t = new Date()
    setH(t.getHours())
    setM(t.getMinutes())
    onChange(`${pad(t.getHours())}:${pad(t.getMinutes())}`)
  }
  const clear = () => {
    onChange('')
    setOpen(false)
  }

  const display = cur ? `${pad(cur.h)}:${pad(cur.m)}` : '--:--'

  return (
    <div className="workhours-time-picker relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={ariaLabel}
        className="workhours-time-input w-full p-3 border border-rule rounded-sm font-mono text-[17px] tabular-nums text-left bg-paper hover:border-ink-soft focus:outline-none focus:border-ink transition-colors flex items-center justify-between"
      >
        <span className={cur ? 'text-ink' : 'text-ink-soft'}>{display}</span>
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          className="text-ink-soft"
          aria-hidden
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </svg>
      </button>

      {open && (
        <div
          className="workhours-time-popover absolute top-full left-0 mt-2 z-30 bg-paper border border-rule rounded-sm p-4 w-[270px] shadow-lg"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="workhours-label text-[12px] uppercase tracking-[0.16em] text-ink-soft font-mono mb-2 text-center">
            {ariaLabel}
          </div>
          <div className="workhours-time-preview text-center font-mono tabular-nums text-[32px] text-ink leading-none mb-4">
            {pad(h)}
            <span className="text-ink-soft mx-1.5">:</span>
            {pad(m)}
          </div>
          <div className="h-px bg-rule mb-3" />
          <div className="flex gap-2">
            <Column ref={hColRef} items={HOURS} selected={h} onSelect={pickH} label="时" />
            <Column ref={mColRef} items={MINUTES} selected={m} onSelect={pickM} label="分" />
          </div>
          <div className="h-px bg-rule mt-4 mb-3" />
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={setNow}
              className="text-[13px] font-mono uppercase tracking-[0.14em] text-navy hover:underline"
            >
              现在
            </button>
            <div className="flex gap-3 ml-auto items-center">
              {value && (
                <button
                  type="button"
                  onClick={clear}
                  className="text-[13px] font-mono uppercase tracking-[0.14em] text-ink-soft hover:text-plum transition-colors"
                >
                  清除
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="px-4 py-2 bg-ink text-paper text-[13px] font-mono uppercase tracking-[0.14em] rounded-sm hover:bg-ink-soft transition-colors"
              >
                确定
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
