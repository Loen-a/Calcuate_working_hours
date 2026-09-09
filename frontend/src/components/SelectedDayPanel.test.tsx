import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import SelectedDayPanel from './SelectedDayPanel'
import type { Day, Preview } from '../lib/types'

const day: Day = {
  date: '2026-09-09', is_workday: true, leave: false, calendar_name: '工作日', manual_override: null,
  entry: { start_time: '08:17', end_time: '19:03' }, actual_minutes: 475,
  daily_balance_minutes: -65, cumulative_balance_minutes: -37, balance_before_minutes: 28,
  required_minutes: null, recommended_minutes: null, suggested_end: null,
  suggested_end_day_offset: null, reason: 'recorded', compliant: false,
}
const preview: Preview = {
  available: true, required_minutes: 577, balance_before_minutes: -37,
  suggested_end: '03:17', suggested_end_label: '次日 03:17', day_offset: 1,
  reason_label: '补足累计欠时',
}
const props = () => ({ day, preview, today: day.date, busy: false, onEdit: vi.fn() })

it('shows authoritative minutes, balance and next-day prediction without deriving them from punches', () => {
  render(<SelectedDayPanel {...props()} />)
  expect(screen.getByRole('heading', { name: day.date })).toBeInTheDocument()
  expect(screen.getByText('今天')).toBeInTheDocument()
  expect(screen.getByText('工作日')).toBeInTheDocument()
  expect(screen.getByText('08:17')).toBeInTheDocument()
  expect(screen.getByText('19:03')).toBeInTheDocument()
  expect(screen.getByText('7h 55m')).toBeInTheDocument()
  expect(screen.getByText('9h 37m')).toBeInTheDocument()
  expect(screen.getByText('−37m')).toBeInTheDocument()
  expect(screen.getByText('次日 03:17')).toBeInTheDocument()
  expect(screen.getByText('补足累计欠时')).toBeInTheDocument()
})

it('keeps a start-only record incomplete, uses server labels and edits only when enabled', () => {
  const input = props()
  input.day = { ...day, entry: { start_time: '23:15', end_time: null }, actual_minutes: null }
  input.preview = { ...preview, required_label: '9 小时 37 分钟', balance_label: '-37 分钟' }
  const { rerender } = render(<SelectedDayPanel {...input} />)
  expect(screen.getByText('23:15')).toBeInTheDocument()
  expect(screen.getByText('--:--')).toBeInTheDocument()
  expect(screen.getByText('待补全')).toBeInTheDocument()
  expect(screen.getByText('9 小时 37 分钟')).toBeInTheDocument()
  expect(screen.getByText('-37 分钟')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '编辑所选日期' }))
  expect(input.onEdit).toHaveBeenCalledTimes(1)
  rerender(<SelectedDayPanel {...input} busy />)
  expect(screen.getByRole('button', { name: '编辑所选日期' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '编辑所选日期' }))
  expect(input.onEdit).toHaveBeenCalledTimes(1)
})

it('preserves overnight punches on leave and suppresses any prediction', () => {
  render(<SelectedDayPanel {...props()} day={{
    ...day, leave: true, is_workday: false, calendar_name: '全天请假',
    entry: { start_time: '22:10', end_time: '07:40' }, actual_minutes: null,
  }} />)
  expect(screen.getByText('全天请假')).toBeInTheDocument()
  expect(screen.getByText('22:10')).toBeInTheDocument()
  expect(screen.getByText('07:40')).toBeInTheDocument()
  expect(screen.getByText(/原打卡记录保留/)).toBeInTheDocument()
  expect(screen.getByText('不计入')).toBeInTheDocument()
  expect(screen.queryByText('次日 03:17')).not.toBeInTheDocument()
  expect(screen.queryByText('9h 37m')).not.toBeInTheDocument()
})

it('asks for a missing start and gives an unavailable reason after a start is present', () => {
  const input = props()
  input.preview = { available: false }
  const { rerender } = render(<SelectedDayPanel {...input} day={{ ...day, entry: null, actual_minutes: null }} />)
  expect(screen.getByText('尚未记录上班时间，填写后查看预测。')).toBeInTheDocument()
  expect(screen.getAllByText('--:--')).toHaveLength(2)
  expect(screen.queryByText('次日 03:17')).not.toBeInTheDocument()
  rerender(<SelectedDayPanel {...input} preview={{ available: false, reason_label: '该日期暂无可用预测' }} />)
  expect(screen.getByText('该日期暂无可用预测')).toBeInTheDocument()
  expect(screen.queryByText(/尚未记录上班时间/)).not.toBeInTheDocument()
})

it('shows preserved complete rest-day punches without labelling them incomplete', () => {
  render(<SelectedDayPanel {...props()} day={{
    ...day, is_workday: false, calendar_name: '手动休息', actual_minutes: null,
  }} preview={{ available: false }} />)
  expect(screen.getByText('休息日')).toBeInTheDocument()
  expect(screen.getByText('手动休息')).toBeInTheDocument()
  expect(screen.getByText('08:17')).toBeInTheDocument()
  expect(screen.getByText('19:03')).toBeInTheDocument()
  expect(screen.getByText('不计入')).toBeInTheDocument()
  expect(screen.queryByText('待补全')).not.toBeInTheDocument()
})
