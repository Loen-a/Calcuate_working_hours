import { useMemo } from 'react'
import type { Entries, HolidayMap } from '../lib/types'
import { dayInfo } from '../lib/holidays'
import { DAILY_TARGET, fmtDate, fmtDuration } from '../lib/workHours'
import { useCountUp } from '../lib/useCountUp'
import { useMonthStats } from '../lib/useMonthStats'

interface Props {
  y: number
  m: number
  entries: Entries
  hMap?: HolidayMap
}

interface CardProps {
  label: string
  value: string
  sub?: string
  tone?: 'ink' | 'navy' | 'plum'
}

function Card({ label, value, sub, tone = 'ink' }: CardProps) {
  const valueColor =
    tone === 'navy' ? 'text-navy' : tone === 'plum' ? 'text-plum' : 'text-ink'
  return (
    <div className="bg-surface border border-rule rounded-sm p-5">
      <div className="text-[14px] uppercase tracking-[0.16em] text-ink-soft font-mono mb-2.5">
        {label}
      </div>
      <div
        className={`font-mono tabular-nums leading-tight text-[24px] ${valueColor}`}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[12px] text-ink-soft mt-2.5 font-mono tabular-nums">
          {sub}
        </div>
      )}
    </div>
  )
}

export default function Dashboard({ y, m, entries, hMap }: Props) {
  const { target, done, entered, balance, wd } = useMonthStats(y, m, entries, hMap)

  // 选目标日：今天（workday 且未打卡）→ 下一个 workday
  const todayDate = new Date()
  const ty = todayDate.getFullYear()
  const tm = todayDate.getMonth() + 1
  const td = todayDate.getDate()
  const todayEntry = entries[fmtDate(ty, tm, td)]
  const todayIsWorkday =
    !!hMap && dayInfo(ty, tm, td, hMap).type === 'work'

  let targetY = ty
  let targetM = tm
  let targetD = td
  if (!(todayIsWorkday && !todayEntry)) {
    const d = new Date(todayDate)
    d.setDate(d.getDate() + 1)
    for (let i = 0; i < 90; i++) {
      const yy = d.getFullYear()
      const mm = d.getMonth() + 1
      const dd = d.getDate()
      const hm = yy === y ? hMap : undefined
      if (dayInfo(yy, mm, dd, hm).type === 'work') {
        targetY = yy
        targetM = mm
        targetD = dd
        break
      }
      d.setDate(d.getDate() + 1)
    }
  }

  // 目标日那个月的余额和剩余工作日（跨月则余额按 0）
  const targetInViewMonth = targetY === y && targetM === m
  const targetBalance = targetInViewMonth ? balance : 0

  const targetRemaining = useMemo(() => {
    const monthDays = new Date(targetY, targetM, 0).getDate()
    let n = 0
    for (let d = targetD; d <= monthDays; d++) {
      const e = entries[fmtDate(targetY, targetM, d)]
      if (e?.leave) continue
      const hm = targetY === y ? hMap : undefined
      if (dayInfo(targetY, targetM, d, hm).type === 'work') n++
    }
    return n
  }, [targetY, targetM, targetD, y, hMap])

  const recommendedEnd = useMemo(() => {
    if (targetRemaining <= 0) return '--:--'
    const perDay = targetBalance / targetRemaining
    let targetNet = 9 - perDay
    targetNet = Math.min(12, Math.max(6, targetNet))
    const endMin = Math.round(8 * 60 + 90 + targetNet * 60)
    const eh = Math.floor(endMin / 60) % 24
    const em = endMin % 60
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${pad(eh)}:${pad(em)}`
  }, [targetBalance, targetRemaining])

  // 目标日标签：今天 / 周X M/D
  const isTargetToday = targetY === ty && targetM === tm && targetD === td
  const targetDateObj = new Date(targetY, targetM - 1, targetD)
  const dayNames = ['日', '一', '二', '三', '四', '五', '六']
  const dayLabel = isTargetToday
    ? '今天'
    : `周${dayNames[targetDateObj.getDay()]} ${targetM}/${targetD}`

  const surplus = balance >= 0
  const animated = useCountUp(balance)

  return (
    <section>
      <div className="bg-surface border border-rule rounded-sm p-5 mb-3">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[13px] uppercase tracking-[0.16em] text-ink-soft font-mono">
            推荐上下班
          </span>
          <span className="text-[11px] uppercase tracking-[0.18em] text-ink-soft font-mono">
            {dayLabel}
          </span>
        </div>
        <div className="flex items-baseline gap-3 font-display font-medium tabular-nums leading-none text-[36px] sm:text-[44px]">
          <span className="text-ink">08:00</span>
          <span className="text-ink-soft text-[24px] sm:text-[28px]">→</span>
          <span
            className={
              recommendedEnd === '--:--' ? 'text-ink-soft' : 'text-ink'
            }
          >
            {recommendedEnd}
          </span>
        </div>
        {recommendedEnd !== '--:--' && targetRemaining > 0 && (
          <div className="text-[12px] text-ink-soft mt-3 font-mono tabular-nums">
            9h 标准 · 分摊 {targetBalance >= 0 ? '+' : '−'}
            {fmtDuration(Math.abs(targetBalance / targetRemaining))} · 还剩{' '}
            {targetRemaining} 个工作日
          </div>
        )}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card
          label="当月目标"
          value={fmtDuration(target)}
          sub={`${wd} 工作日 × ${fmtDuration(DAILY_TARGET)}`}
        />
        <Card
          label="已完成"
          value={fmtDuration(done)}
          sub={`已录入 ${entered} 天`}
        />
        <Card
          label={surplus ? '盈余' : '缺口'}
          value={`${surplus ? '+' : '−'}${fmtDuration(Math.abs(animated))}`}
          tone={surplus ? 'navy' : 'plum'}
          sub={`按已录入 × ${fmtDuration(DAILY_TARGET)}`}
        />
        <Card label="工作日" value={`${entered}/${wd}`} sub="计入 / 本月工作日" />
      </div>
    </section>
  )
}
