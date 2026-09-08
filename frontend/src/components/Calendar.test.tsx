import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import Calendar from './Calendar'
import type { Day } from '../lib/types'

const restDay: Day = {
  date: '2026-09-06', is_workday: false, leave: false, calendar_name: '休息日', manual_override: null,
  entry: { start_time: '08:00', end_time: '18:30' }, actual_minutes: null, daily_balance_minutes: null,
  cumulative_balance_minutes: null, balance_before_minutes: 0, required_minutes: null,
  recommended_minutes: null, suggested_end: null, suggested_end_day_offset: null, reason: '', compliant: null,
}
it('identifies a complete uncounted rest-day record without requesting more punches', () => {
  render(<Calendar selected={restDay.date} today={restDay.date} days={[restDay]} busy={false} onPick={vi.fn()} />)
  const cell = within(screen.getByRole('button', { name: `编辑 ${restDay.date}` }))
  expect(cell.getByText('已记录')).toHaveAttribute('title', '已记录 · 不计工时')
  expect(cell.queryByText('待补全')).not.toBeInTheDocument()
})
it('only asks to complete a record when an endpoint is missing', () => {
  render(<Calendar selected={restDay.date} today={restDay.date} days={[{ ...restDay, entry: { start_time: '08:00', end_time: null } }]} busy={false} onPick={vi.fn()} />)
  expect(within(screen.getByRole('button', { name: `编辑 ${restDay.date}` })).getByText('待补全')).toBeInTheDocument()
})
it('renders and selects the actual four-digit year before 0100', () => {
  const onPick = vi.fn()
  render(<Calendar selected="0099-09-08" today="2026-09-08" days={[]} busy={false} onPick={onPick} />)
  fireEvent.click(screen.getByRole('button', { name: '编辑 0099-09-08' }))
  expect(onPick).toHaveBeenCalledWith('0099-09-08')
  expect(screen.queryByRole('button', { name: '编辑 1999-09-08' })).not.toBeInTheDocument()
})
