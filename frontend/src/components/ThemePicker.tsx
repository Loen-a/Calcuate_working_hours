import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { THEMES } from '../lib/themes'
import type { Theme } from '../lib/types'

interface Props { theme: Theme; disabled: boolean; buttonClass: string; onSelect: (theme: Theme) => void }

export default function ThemePicker({ theme, disabled, buttonClass, onSelect }: Props) {
  const menuId = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const options = useRef<Array<HTMLButtonElement | null>>([])
  const restoreFocus = useRef(false)
  const [open, setOpen] = useState(false)
  const [focused, setFocused] = useState(0)
  const [position, setPosition] = useState({ top: 0, left: 0, width: 280, maxHeight: 400 })
  const selectedIndex = Math.max(0, THEMES.findIndex(option => option.id === theme))

  const close = (returnFocus: boolean) => {
    restoreFocus.current = returnFocus
    setOpen(false)
  }
  const show = () => {
    if (disabled) return
    restoreFocus.current = false
    setFocused(selectedIndex)
    setOpen(true)
  }
  useEffect(() => { if (disabled) setOpen(false) }, [disabled])
  useLayoutEffect(() => {
    if (open) options.current[focused]?.focus()
    else if (!disabled && restoreFocus.current) {
      restoreFocus.current = false
      // 保存期间按钮会暂时禁用；完成后只恢复尚未移到其他控件的焦点。
      if (document.activeElement === document.body || document.activeElement === trigger.current) trigger.current?.focus()
    }
  }, [open, focused, disabled])
  useLayoutEffect(() => {
    if (!open) return
    const place = () => {
      const anchor = trigger.current?.getBoundingClientRect()
      if (!anchor || !menu.current) return
      const margin = 12, gap = 8
      const width = Math.max(1, Math.min(280, window.innerWidth - margin * 2))
      const height = Math.min(menu.current.scrollHeight, Math.max(1, window.innerHeight - margin * 2))
      const below = window.innerHeight - anchor.bottom - margin - gap
      const preferredTop = below >= height || below >= anchor.top - margin ? anchor.bottom + gap : anchor.top - gap - height
      const top = Math.max(margin, Math.min(preferredTop, window.innerHeight - margin - height))
      const left = Math.max(margin, Math.min(anchor.right - width, window.innerWidth - margin - width))
      setPosition({ top, left, width, maxHeight: Math.max(1, window.innerHeight - top - margin) })
    }
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !menu.current?.contains(event.target) && !trigger.current?.contains(event.target)) close(false)
    }
    place()
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    document.addEventListener('pointerdown', outside)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
      document.removeEventListener('pointerdown', outside)
    }
  }, [open])

  return <>
    <button ref={trigger} type="button" disabled={disabled} className={`${buttonClass} workhours-theme-trigger`}
      aria-haspopup="menu" aria-expanded={open} aria-controls={open ? menuId : undefined} title="选择界面风格"
      onClick={() => open ? close(true) : show()}
      onKeyDown={event => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); show() }
        else if (event.key === 'Escape' && open) { event.preventDefault(); close(true) }
      }}>
      {THEMES[selectedIndex].label}
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d={open ? 'm4 10 4-4 4 4' : 'm4 6 4 4 4-4'} /></svg>
    </button>
    {open && createPortal(<div ref={menu} id={menuId} className="workhours-theme-menu" role="menu" aria-label="界面风格" style={position}
      onKeyDown={event => {
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true) }
        else if (event.key === 'Tab') {
          close(false)
          // 浮层在 body 末尾，显式回到触发按钮相邻的文档焦点顺序。
          const controls = Array.from(document.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea, [tabindex]'))
            .filter(element => !menu.current?.contains(element) && element.tabIndex >= 0
              && !element.matches(':disabled, [type="hidden"]')
              && (typeof element.checkVisibility !== 'function' || element.checkVisibility()))
          const index = controls.indexOf(trigger.current!)
          const next = controls[index + (event.shiftKey ? -1 : 1)]
          if (index >= 0 && next) { event.preventDefault(); next.focus() }
          else trigger.current?.focus()
        } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
          event.preventDefault()
          setFocused(index => event.key === 'Home' ? 0 : event.key === 'End' ? THEMES.length - 1
            : (index + (event.key === 'ArrowDown' ? 1 : -1) + THEMES.length) % THEMES.length)
        }
      }}>
      <p className="workhours-theme-menu-label">界面风格</p>
      {THEMES.map((option, index) => <button key={option.id} ref={element => { options.current[index] = element }}
        type="button" role="menuitemradio" disabled={disabled} aria-checked={theme === option.id} tabIndex={focused === index ? 0 : -1}
        className="workhours-theme-option" onFocus={() => setFocused(index)}
        onClick={() => { close(true); if (option.id !== theme) onSelect(option.id) }}>
        <span className="workhours-theme-swatches" aria-hidden="true">{option.colors.map(color => <i key={color} style={{ backgroundColor: color }} />)}</span>
        <span>{option.label}</span>
        <svg className="workhours-theme-check" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          {theme === option.id && <path d="m3 8 3 3 7-7" />}
        </svg>
      </button>)}
    </div>, document.body)}
  </>
}
