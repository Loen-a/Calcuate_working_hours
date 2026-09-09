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
  const cell = within(screen.getByRole('button', { name: `选择 ${restDay.date}` }))
  expect(cell.getByText('已记录')).toHaveAttribute('title', '已记录 · 不计工时')
  expect(cell.queryByText('待补全')).not.toBeInTheDocument()
})
it('only asks to complete a record when an endpoint is missing', () => {
  render(<Calendar selected={restDay.date} today={restDay.date} days={[{ ...restDay, entry: { start_time: '08:00', end_time: null } }]} busy={false} onPick={vi.fn()} />)
  expect(within(screen.getByRole('button', { name: `选择 ${restDay.date}` })).getByText('待补全')).toBeInTheDocument()
})
it('renders and selects the actual four-digit year before 0100', () => {
  const onPick = vi.fn()
  render(<Calendar selected="0099-09-08" today="2026-09-08" days={[]} busy={false} onPick={onPick} />)
  fireEvent.click(screen.getByRole('button', { name: '选择 0099-09-08' }))
  expect(onPick).toHaveBeenCalledWith('0099-09-08')
  expect(screen.queryByRole('button', { name: '选择 1999-09-08' })).not.toBeInTheDocument()
})

it.each([
  { minutes: 30, label: '+30m', sign: 'positive' },
  { minutes: -30, label: '−30m', sign: 'negative' },
  { minutes: 0, label: '0m', sign: 'zero' },
])('exposes the $sign balance for theme-specific colors without changing its value', ({ minutes, label, sign }) => {
  const day = { ...restDay, is_workday: true, calendar_name: '工作日', actual_minutes: 540 + minutes, daily_balance_minutes: minutes }
  render(<Calendar selected={day.date} today={day.date} days={[day]} busy={false} onPick={vi.fn()} />)
  const cell = within(screen.getByRole('button', { name: `选择 ${day.date}` }))
  expect(cell.getByText(label)).toHaveAttribute('data-balance-sign', sign)
})

it.each([
  { date: '2021-02-10', rows: 4 },
  { date: '2026-09-08', rows: 5 },
  { date: '2026-08-08', rows: 6 },
])('uses $rows calendar weeks on desktop for $date', ({ date, rows }) => {
  render(<Calendar selected={date} today="2026-09-09" days={[]} busy={false} onPick={vi.fn()} />)
  const table = screen.getByRole('table')
  expect(within(table).getAllByRole('row')).toHaveLength(rows + 1)
  expect(within(table).getAllByRole('button')).toHaveLength(rows * 7)
  expect(screen.getByRole('heading', { name: '工时日历' })).toBeInTheDocument()
})

it('marks the desktop selection separately from today and passes adjacent-month dates unchanged', () => {
  const onPick = vi.fn()
  render(<Calendar selected="2026-09-08" today="2026-09-09" days={[]} busy={false} onPick={onPick} />)
  expect(screen.getByRole('button', { name: '选择 2026-09-08', pressed: true })).toBeInTheDocument()
  const today = screen.getByRole('button', { name: '选择 2026-09-09', pressed: false })
  expect(today).toHaveAttribute('aria-current', 'date')
  fireEvent.click(screen.getByRole('button', { name: '选择 2026-08-31' }))
  fireEvent.click(screen.getByRole('button', { name: '选择 2026-10-04' }))
  expect(onPick.mock.calls).toEqual([['2026-08-31'], ['2026-10-04']])
})


it.each(['0099-09-08', '0004-02-29'])('preserves low years and leap dates in desktop selection: %s', date => {
  const onPick = vi.fn()
  render(<Calendar selected={date} today="2026-09-09" days={[]} busy={false} onPick={onPick} />)
  fireEvent.click(screen.getByRole('button', { name: `选择 ${date}`, pressed: true }))
  expect(onPick).toHaveBeenCalledWith(date)
})

it.each([
  { finalDate: '2026-09-09', outcome: 'successful' },
  { finalDate: '2026-09-08', outcome: 'failed' },
])('restores the selected PC date focus after a $outcome calendar request', ({ finalDate }) => {
  const onPick = vi.fn()
  const view = (selected: string, busy: boolean) => <Calendar selected={selected} today="2026-09-09" days={[]} busy={busy} onPick={onPick} />
  const { rerender } = render(view('2026-09-08', false))
  const requested = screen.getByRole('button', { name: '选择 2026-09-09' })
  expect(screen.getByRole('button', { name: '选择 2026-09-08' })).not.toHaveFocus()
  requested.focus()
  fireEvent.click(requested)
  expect(onPick).toHaveBeenCalledWith('2026-09-09')
  // Blur before disabling because jsdom cannot blur an already disabled button like Chrome does.
  requested.blur()
  rerender(view('2026-09-08', true))
  expect(document.body).toHaveFocus()
  rerender(view(finalDate, false))
  expect(screen.getByRole('button', { name: `选择 ${finalDate}`, pressed: true })).toHaveFocus()
})

it.each([false, true])('does not reclaim focus after the user moves to another control (then blurs: %s)', blurOther => {
  const view = (selected: string, busy: boolean) => <>
    <button type="button">其他操作</button>
    <Calendar selected={selected} today="2026-09-09" days={[]} busy={busy} onPick={vi.fn()} />
  </>
  const { rerender } = render(view('2026-09-08', false))
  const requested = screen.getByRole('button', { name: '选择 2026-09-09' })
  requested.focus()
  fireEvent.click(requested)
  rerender(view('2026-09-08', true))
  const other = screen.getByRole('button', { name: '其他操作' })
  other.focus()
  if (blurOther) other.blur()
  rerender(view('2026-09-09', false))
  expect(blurOther ? document.body : other).toHaveFocus()
})

it('does not focus a calendar cell after an unrelated busy cycle such as a theme change', () => {
  const view = (busy: boolean) => <Calendar selected="2026-09-08" today="2026-09-09" days={[]} busy={busy} onPick={vi.fn()} />
  const { rerender } = render(view(false))
  rerender(view(true))
  rerender(view(false))
  expect(document.body).toHaveFocus()
})


it('shows provided PC weather without replacing leave/rest labels or adding a separate action', () => {
  const weather = { loading: false, error: null, data: {
    city: '杭州', timezone: 'Asia/Shanghai', month: '2026-09', forecast_start: '2026-09-06', forecast_end: '2026-09-12',
    source: 'cache', stale: false, fetched_at: '2026-09-06T00:00:00Z', warning: null,
    days: { '2026-09-06': { code: 61, description: '小雨', icon: 'rain', temperature_min: 23.4, temperature_max: 29.1 } },
  } } as const
  const onPick = vi.fn()
  render(<Calendar selected={restDay.date} today={restDay.date} days={[restDay]} busy={false} onPick={onPick} weather={weather} />)
  const cell = within(screen.getByRole('button', { name: `选择 ${restDay.date}` }))
  expect(cell.getByText('休')).toBeInTheDocument()
  expect(cell.getByText('休息日')).toBeInTheDocument()
  const forecast = cell.getByTitle(/^小雨，最低 23.4°C，最高 29.1°C/)
  expect(forecast).not.toHaveAttribute('tabindex')
  fireEvent.click(forecast)
  expect(onPick).toHaveBeenCalledWith(restDay.date)
  expect(screen.getByRole('link', { name: 'Open-Meteo' })).toHaveAttribute('href', 'https://open-meteo.com/')
})

it('never invents sunny weather for null records or dates outside the returned forecast window', () => {
  const weather = { loading: false, error: null, data: {
    city: '杭州', timezone: 'Asia/Shanghai', month: '2026-09', forecast_start: '2026-09-06', forecast_end: '2026-09-12',
    source: 'cache', stale: false, fetched_at: null, warning: null,
    days: {
      '2026-09-06': null,
      '2026-09-05': { code: 0, description: '晴', icon: 'clear', temperature_min: 20, temperature_max: 30 },
      '2026-09-13': { code: 0, description: '晴', icon: 'clear', temperature_min: 20, temperature_max: 30 },
    },
  } }
  render(<Calendar selected={restDay.date} today={restDay.date} days={[{ ...restDay, leave: true, calendar_name: '全天请假' }]} busy={false} onPick={vi.fn()} weather={weather as never} />)
  const cell = within(screen.getByRole('button', { name: `选择 ${restDay.date}` }))
  expect(cell.getByText('假')).toBeInTheDocument()
  expect(cell.getByText('全天请假')).toBeInTheDocument()
  expect(screen.queryByTitle('晴，最低 20°C，最高 30°C')).not.toBeInTheDocument()
  expect(screen.queryByText('20°/30°')).not.toBeInTheDocument()
})

it('explains an out-of-range forecast month without claiming an automatic retry will provide its weather', () => {
  const warning = '所选月份暂无预报，仅提供杭州今天起七天的天气。'
  const weather = { loading: false, error: null, data: {
    city: '杭州', timezone: 'Asia/Shanghai', month: '2026-10', forecast_start: '2026-09-09', forecast_end: '2026-09-15',
    source: 'unavailable', stale: false, fetched_at: null, warning, days: {},
  } } as const
  render(<Calendar selected="2026-10-01" today="2026-09-09" days={[]} busy={false} onPick={vi.fn()} weather={weather} />)
  expect(screen.getByText(warning)).toBeInTheDocument()
  expect(screen.getByText('7天预报（°C）')).toBeInTheDocument()
  expect(screen.queryByText('天气暂不可用，稍后自动重试')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '选择 2026-10-01' })).toBeEnabled()
})
