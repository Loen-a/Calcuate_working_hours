import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './lib/api'

vi.mock('./lib/api')

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

const currentYear = new Date().getFullYear()
const currentMonth = String(new Date().getMonth() + 1).padStart(2, '0')

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.getEntries).mockResolvedValue({})
  vi.mocked(api.getPreferences).mockResolvedValue({ theme: 'teal' })
  vi.mocked(api.getHolidays).mockResolvedValue({
    year: currentYear,
    holidays: {},
    source: 'cache',
  })
  vi.mocked(api.importBackup).mockResolvedValue({ version: 1, entries: 0, holidayYears: 1 })
  vi.mocked(api.putPreferences).mockResolvedValue({ theme: 'cool' })
  vi.spyOn(window, 'alert').mockImplementation(() => undefined)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

it('loads all persistent state from the backend before showing the app', async () => {
  render(<App />)

  expect(screen.getByText('正在连接本地数据库…')).toBeInTheDocument()
  expect(await screen.findByText('Workhours')).toBeInTheDocument()
  expect(api.getEntries).toHaveBeenCalledOnce()
  expect(api.getPreferences).toHaveBeenCalledOnce()
  expect(api.getHolidays).toHaveBeenCalled()
  expect(document.documentElement).toHaveAttribute('data-theme', 'teal')
})

it('ignores an older holiday response after the post-import reload starts', async () => {
  const initialHoliday = deferred<api.HolidayApiResponse>()
  const importedHoliday = deferred<api.HolidayApiResponse>()
  vi.mocked(api.getHolidays)
    .mockReturnValueOnce(initialHoliday.promise)
    .mockReturnValueOnce(importedHoliday.promise)

  render(<App />)
  await screen.findByText('Workhours')

  const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]')!
  fireEvent.change(fileInput, {
    target: { files: [new File(['{}'], 'backup.json', { type: 'application/json' })] },
  })
  await waitFor(() => expect(api.getHolidays).toHaveBeenCalledTimes(2))

  await act(async () => {
    importedHoliday.resolve({
      year: currentYear,
      holidays: { [`${currentMonth}-01`]: { name: '导入后数据', isOffDay: true } },
      source: 'cache',
    })
  })
  expect(await screen.findByText('导入后数据')).toBeInTheDocument()

  await act(async () => {
    initialHoliday.resolve({
      year: currentYear,
      holidays: { [`${currentMonth}-01`]: { name: '过期数据', isOffDay: true } },
      source: 'remote',
    })
  })
  expect(screen.queryByText('过期数据')).not.toBeInTheDocument()
  expect(screen.getByText('导入后数据')).toBeInTheDocument()
})

it('blocks year and persistent actions during import and reloads the viewed year', async () => {
  const importing = deferred<{ version: number; entries: number; holidayYears: number }>()
  vi.mocked(api.importBackup).mockReturnValue(importing.promise)

  const { container } = render(<App />)
  await screen.findByText('Workhours')
  const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]')!
  const previousButton = screen.getByRole('button', { name: '上一月' })
  const nextButton = screen.getByRole('button', { name: '下一月' })
  const themeButton = screen.getByRole('button', { name: '青绿' })

  for (let i = 1; i < new Date().getMonth() + 1; i++) fireEvent.click(previousButton)

  await act(async () => {
    fireEvent.click(previousButton)
    fireEvent.change(fileInput, {
      target: { files: [new File(['{}'], 'backup.json', { type: 'application/json' })] },
    })
    fireEvent.click(nextButton)
    fireEvent.click(themeButton)
    fireEvent.click(container.querySelector('tbody td')!)
  })

  expect(api.importBackup).toHaveBeenCalledOnce()
  expect(api.putPreferences).not.toHaveBeenCalled()
  expect(nextButton).toBeDisabled()
  expect(themeButton).toBeDisabled()
  expect(screen.queryByText('Entry')).not.toBeInTheDocument()

  await act(async () => {
    importing.resolve({ version: 1, entries: 0, holidayYears: 1 })
  })
  await waitFor(() => expect(api.getHolidays).toHaveBeenLastCalledWith(currentYear - 1))
})

it('does not start import while another persistent mutation is active', async () => {
  const savingTheme = deferred<{ theme: 'cool' }>()
  vi.mocked(api.putPreferences).mockReturnValue(savingTheme.promise)

  const { container } = render(<App />)
  await screen.findByText('Workhours')

  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: '青绿' }))
    fireEvent.change(container.querySelector<HTMLInputElement>('input[type="file"]')!, {
      target: { files: [new File(['{}'], 'backup.json', { type: 'application/json' })] },
    })
  })

  expect(api.putPreferences).toHaveBeenCalledOnce()
  expect(api.importBackup).not.toHaveBeenCalled()

  await act(async () => {
    savingTheme.resolve({ theme: 'cool' })
  })
})

it('blocks the app when upload succeeds but authoritative reload fails', async () => {
  vi.mocked(api.getEntries)
    .mockResolvedValueOnce({ '2026-07-01': { in: '08:00', out: '18:30' } })
    .mockRejectedValueOnce(new Error('数据库连接已断开'))

  const { container } = render(<App />)
  await screen.findByText('Workhours')

  fireEvent.change(container.querySelector<HTMLInputElement>('input[type="file"]')!, {
    target: { files: [new File(['{}'], 'backup.json', { type: 'application/json' })] },
  })

  expect(
    await screen.findByText(/导入已完成，但重新读取失败.*数据库连接已断开.*刷新.*重新连接/),
  ).toBeInTheDocument()
  expect(screen.queryByText('Workhours')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '导入' })).not.toBeInTheDocument()
  expect(window.alert).not.toHaveBeenCalledWith(expect.stringContaining('导入失败'))
})
