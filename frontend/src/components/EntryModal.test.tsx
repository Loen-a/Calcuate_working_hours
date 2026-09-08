import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import EntryModal from './EntryModal'
import type { Day } from '../lib/types'
import { getPreview } from '../lib/api'

vi.mock('../lib/api', () => ({ getPreview: vi.fn() }))
vi.mock('./TimePicker', () => ({ default: ({ value, onChange, ariaLabel }: { value: string; onChange: (value: string) => void; ariaLabel: string }) =>
  <input aria-label={ariaLabel} value={value} onChange={event => onChange(event.target.value)} /> }))
const day: Day = {
  date: '2026-09-08', is_workday: true, leave: false, calendar_name: '工作日', manual_override: null,
  entry: { start_time: '08:17', end_time: null }, actual_minutes: null, daily_balance_minutes: null,
  cumulative_balance_minutes: null, balance_before_minutes: 0, required_minutes: 540,
  recommended_minutes: 540, suggested_end: '18:47', suggested_end_day_offset: 0, reason: '', compliant: null,
}
const preview = { available: true, suggested_end: '18:47', required_label: '9 小时' }
const callbacks = () => ({ externalBusy: false, onClose: vi.fn(), onSave: vi.fn().mockResolvedValue(undefined),
  onDelete: vi.fn().mockResolvedValue(undefined), onLeave: vi.fn().mockResolvedValue(undefined), onCalendar: vi.fn().mockResolvedValue(undefined) })
beforeEach(() => vi.mocked(getPreview).mockResolvedValue(preview))
it('uses the current start time for authoritative preview and ignores a stale response', async () => {
  let finishOld!: (value: typeof preview) => void
  vi.mocked(getPreview).mockReturnValueOnce(new Promise(resolve => { finishOld = resolve }))
    .mockResolvedValueOnce({ ...preview, suggested_end: '23:19' })
  render(<EntryModal day={day} preview={preview} {...callbacks()} />)
  fireEvent.change(screen.getByLabelText('上班 · In'), { target: { value: '10:00' } })
  await waitFor(() => expect(getPreview).toHaveBeenCalledWith(day.date, '10:00', expect.any(AbortSignal)))
  fireEvent.change(screen.getByLabelText('上班 · In'), { target: { value: '12:00' } })
  expect(await screen.findByText('23:19')).toBeInTheDocument()
  await act(async () => { finishOld({ ...preview, suggested_end: '20:11' }) })
  expect(screen.queryByText('20:11')).not.toBeInTheDocument()
  expect(screen.getByText('23:19')).toBeInTheDocument()
})
it('cancels leave through its own API operation and never saves synthetic punches', async () => {
  const props = callbacks()
  render(<EntryModal day={{ ...day, leave: true, entry: null }} preview={{ available: false }} {...props} />)
  fireEvent.click(screen.getByRole('button', { name: '取消全天请假' }))
  await waitFor(() => expect(props.onLeave).toHaveBeenCalledWith(false))
  expect(props.onSave).not.toHaveBeenCalled()
  expect(props.onDelete).not.toHaveBeenCalled()
})
it('keeps editing available after a failed calendar update', async () => {
  const props = callbacks()
  props.onCalendar.mockRejectedValue(new Error('日历保存失败'))
  render(<EntryModal day={day} preview={preview} {...props} />)
  fireEvent.change(screen.getByLabelText('手动日历标记'), { target: { value: 'holiday' } })
  fireEvent.click(screen.getByRole('button', { name: '应用日历' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('日历保存失败')
  expect(props.onCalendar).toHaveBeenCalledWith('holiday')
  expect(props.onClose).not.toHaveBeenCalled()
  expect(screen.getByLabelText('上班 · In')).toHaveValue('08:17')
})
