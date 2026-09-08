import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'

const date = '2026-09-08'
const makeDashboard = () => ({
  today: date, selected_date: date, theme: 'teal',
  settings: { period: 'month', target_minutes_per_day: 540, minimum_minutes_per_day: 480 },
  intervals: [{ interval_id: 1, name: '午休', start_time: '12:00', end_time: '13:00', enabled: true }],
  days: Array.from({ length: 30 }, (_, i) => ({
    date: `2026-09-${String(i + 1).padStart(2, '0')}`, is_workday: true, leave: false,
    calendar_name: '工作日', manual_override: null,
    entry: i === 7 ? { start_time: '10:13', end_time: null as string | null } : null,
    actual_minutes: null, daily_balance_minutes: null, cumulative_balance_minutes: null,
    balance_before_minutes: -37, required_minutes: 577, recommended_minutes: 600,
    suggested_end: '21:17', suggested_end_day_offset: 0, reason: 'balance', compliant: null,
  })),
  selected_preview: { available: true, required_minutes: 577, required_label: '9 小时 37 分钟',
    balance_before_minutes: -37, balance_label: '-37 分钟', reason_label: '补足历史欠时',
    suggested_end: '21:17', suggested_end_label: '21:17', day_offset: 0 },
  month: { start: '2026-09-01', end: '2026-09-30', target_minutes: 11340, completed_minutes: 1503,
    balance_minutes: -37, remaining_target_minutes: 9837, workday_count: 21,
    recorded_days: 3, missing_history_days: ['2026-09-07'] },
  forecast: { period_start: '2026-09-01', period_end: '2026-09-30', target_minutes: 11340,
    completed_minutes: 1503, remaining_target_minutes: 9837, carryover_minutes: -37, goal_met: false },
  holiday_status: { year: 2026, source: 'cache', warning: null },
})

let dashboard = makeDashboard()
const requests: { path: string; init?: RequestInit }[] = []
let importError = ''
let entryError = ''
let dashboardError = ''
let settingsError = ''
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

beforeEach(() => {
  dashboard = makeDashboard()
  requests.length = 0
  importError = ''
  entryError = ''
  dashboardError = ''
  settingsError = ''
  window.history.replaceState({}, '', `/?reference_date=${date}`)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  vi.spyOn(window, 'alert').mockImplementation(() => undefined)
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const path = new URL(input, window.location.origin).pathname
    requests.push({ path, init })
    if (path === '/api/dashboard') {
      if (dashboardError) return json({ error: dashboardError }, 503)
      const selected = new URL(input, window.location.origin).searchParams.get('reference_date') || date
      return json({ ...dashboard, selected_date: selected })
    }
    if (path === '/api/settings' && init?.method === 'PUT') {
      if (settingsError) return json({ error: settingsError }, 400)
      const settings = JSON.parse(init.body as string)
      if (settings.theme) dashboard.theme = settings.theme
      return json({ ok: true })
    }
    if (path === '/preview/earliest-end') return json(dashboard.selected_preview)
    if (path === '/api/backup' && init?.method === 'POST') {
      return importError ? json({ error: importError }, 400) : json({ version: 3, entries: 1 })
    }
    if (path.startsWith('/api/entries/') && entryError) return json({ error: entryError }, 400)
    // Allow the original interface to render so red exposes its client-side calculation.
    if (path === '/api/entries') return json({})
    if (path === '/api/preferences') return json({ theme: 'teal' })
    if (path === '/api/holidays/2026') return json({ year: 2026, holidays: {}, source: 'cache' })
    return json({ ok: true })
  }))
})

it('uses the server prediction and monthly totals, and preserves the selected date in the interface switch', async () => {
  render(<App />)
  expect(await screen.findByText('21:17')).toBeInTheDocument()
  expect(screen.getByText('189h')).toBeInTheDocument()
  expect(screen.getByText('25h 03m')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '切换旧界面' })).toHaveAttribute('href', `/interface/old?reference_date=${date}`)
  expect(document.documentElement).toHaveAttribute('data-theme', 'teal')
  fireEvent.click(screen.getByRole('button', { name: '编辑 2026-09-09' }))
  await screen.findByRole('dialog')
  expect(screen.getByRole('link', { name: '切换旧界面' })).toHaveAttribute('href', '/interface/old?reference_date=2026-09-09')
})

it('saves a start-only record without inventing an end time', async () => {
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: `编辑 ${date}` }))
  await screen.findByRole('dialog')
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '保存打卡' }))
  await waitFor(() => expect(requests.some(r => r.path === `/api/entries/${date}`)).toBe(true))
  const saved = requests.find(r => r.path === `/api/entries/${date}`)!
  expect(JSON.parse(saved.init!.body as string)).toEqual({ start_time: '10:13', end_time: null })
})

it('saves cross-midnight punches and retains inputs when saving fails', async () => {
  dashboard.days[7].entry = { start_time: '22:10', end_time: '07:40' }
  entryError = '数据库写入失败'
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: `编辑 ${date}` }))
  await screen.findByRole('dialog')
  fireEvent.click(screen.getByRole('button', { name: '保存打卡' }))
  expect(await screen.findByText('数据库写入失败')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '上班 · In' })).toHaveTextContent('22:10')
  expect(screen.getByRole('button', { name: '下班 · Out' })).toHaveTextContent('07:40')
  expect(JSON.parse(requests.find(r => r.path === `/api/entries/${date}`)!.init!.body as string))
    .toEqual({ start_time: '22:10', end_time: '07:40' })
})

it('sets leave independently without overwriting preserved punches', async () => {
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: `编辑 ${date}` }))
  await screen.findByRole('dialog')
  fireEvent.click(screen.getByRole('button', { name: '设为全天请假' }))
  await waitFor(() => expect(requests.some(r => r.path === `/api/leaves/${date}`)).toBe(true))
  expect(JSON.parse(requests.find(r => r.path === `/api/leaves/${date}`)!.init!.body as string)).toEqual({ enabled: true })
  expect(requests.some(r => r.path.startsWith('/api/entries/'))).toBe(false)
})

it('always confirms replacement without punches and reports failed import', async () => {
  dashboard.days.forEach(day => { day.entry = null })
  render(<App />)
  await screen.findByText('Workhours')
  const fileInput = screen.getByLabelText('选择 JSON 备份')
  const file = new File(['{}'], 'backup.json', { type: 'application/json' })
  vi.mocked(window.confirm).mockReturnValueOnce(false)
  fireEvent.change(fileInput, { target: { files: [file] } })
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('覆盖'))
  expect(requests.some(r => r.path === '/api/backup')).toBe(false)
  importError = '备份格式不兼容'
  fireEvent.change(fileInput, { target: { files: [file] } })
  expect(await screen.findByRole('alert')).toHaveTextContent('备份格式不兼容')
  expect(screen.queryByText(/导入成功/)).not.toBeInTheDocument()
})

it('blocks stale data after import succeeds but authoritative reload fails', async () => {
  render(<App />)
  await screen.findByText('Workhours')
  dashboardError = '数据库连接已断开'
  fireEvent.change(screen.getByLabelText('选择 JSON 备份'), {
    target: { files: [new File(['{}'], 'backup.json', { type: 'application/json' })] },
  })
  expect(await screen.findByRole('alert')).toHaveTextContent('导入已完成，但重新读取失败')
  expect(screen.queryByRole('button', { name: '导入' })).not.toBeInTheDocument()
})

it('locks navigation and other writes while importing, then refreshes the same selected date', async () => {
  let finish!: (response: Response) => void
  const originalFetch = vi.mocked(fetch).getMockImplementation()!
  vi.mocked(fetch).mockImplementation((input, init) => {
    if (String(input) === '/api/backup' && init?.method === 'POST') return new Promise(resolve => { finish = resolve })
    return originalFetch(input, init)
  })
  render(<App />)
  await screen.findByText('Workhours')
  fireEvent.change(screen.getByLabelText('选择 JSON 备份'), {
    target: { files: [new File(['{}'], 'backup.json', { type: 'application/json' })] },
  })
  expect(await screen.findByRole('button', { name: '导入中…' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '下一月' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '青绿' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: `编辑 ${date}` }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  finish(json({ version: 3, entries: 2 }))
  expect(await screen.findByRole('status')).toHaveTextContent('导入成功，共 2 条记录')
  expect(screen.getByRole('link', { name: '切换旧界面' })).toHaveAttribute('href', `/interface/old?reference_date=${date}`)
  expect(screen.getByRole('button', { name: '下一月' })).toBeEnabled()
})

it('reports a failed holiday refresh with retained cache instead of claiming success', async () => {
  const originalFetch = vi.mocked(fetch).getMockImplementation()!
  vi.mocked(fetch).mockImplementation((input, init) => {
    if (String(input) === '/api/holidays/2026/refresh') return Promise.resolve(json({ year: 2026, source: 'cache', warning: '获取失败，继续使用缓存' }))
    return originalFetch(input, init)
  })
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '刷新节假日' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('获取失败，继续使用缓存')
  expect(screen.queryByText('2026 年节假日已刷新')).not.toBeInTheDocument()
})


function mockDesktopViewport(initialDesktop: boolean) {
  let desktop = initialDesktop
  const listeners = new Set<() => void>()
  vi.spyOn(window, 'matchMedia').mockImplementation(query => ({
    get matches() { return query.includes('min-width') ? desktop : true },
    media: query,
    onchange: null,
    addEventListener: (_event: string, callback: () => void) => { listeners.add(callback) },
    removeEventListener: (_event: string, callback: () => void) => { listeners.delete(callback) },
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => true,
  } as unknown as MediaQueryList))
  return (next: boolean) => { desktop = next; listeners.forEach(listener => listener()) }
}

it('cycles the desktop theme through cool, teal and classic using persisted responses', async () => {
  mockDesktopViewport(true)
  dashboard.theme = 'cool'
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '冷色' }))
  fireEvent.click(await screen.findByRole('button', { name: '青绿' }))
  fireEvent.click(await screen.findByRole('button', { name: '经典绿' }))
  expect(await screen.findByRole('button', { name: '冷色' })).toBeInTheDocument()
  expect(requests.filter(request => request.path === '/api/settings').map(request => JSON.parse(request.init!.body as string).theme))
    .toEqual(['teal', 'classic', 'cool'])
})

it('displays classic theme as cool on mobile and restores classic after resize without writing settings', async () => {
  const resize = mockDesktopViewport(false)
  dashboard.theme = 'classic'
  render(<App />)
  expect(await screen.findByRole('button', { name: '冷色' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '经典绿' })).not.toBeInTheDocument()
  await act(async () => resize(true))
  expect(screen.getByRole('button', { name: '经典绿' })).toBeInTheDocument()
  await act(async () => resize(false))
  expect(screen.getByRole('button', { name: '冷色' })).toBeInTheDocument()
  await act(async () => resize(true))
  expect(screen.getByRole('button', { name: '经典绿' })).toBeInTheDocument()
  expect(dashboard.theme).toBe('classic')
  expect(requests.some(request => request.path === '/api/settings')).toBe(false)
})

it('saves teal only when the mobile user clicks the cool fallback of classic theme', async () => {
  mockDesktopViewport(false)
  dashboard.theme = 'classic'
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '冷色' }))
  expect(await screen.findByRole('button', { name: '青绿' })).toBeInTheDocument()
  expect(JSON.parse(requests.find(request => request.path === '/api/settings')!.init!.body as string)).toEqual({ theme: 'teal' })
  expect(document.documentElement).toHaveAttribute('data-theme', 'teal')
})

it('keeps the previous theme visible when saving classic theme fails', async () => {
  mockDesktopViewport(true)
  settingsError = '主题保存失败，请重试'
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '青绿' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('主题保存失败，请重试')
  expect(screen.getByRole('button', { name: '青绿' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '经典绿' })).not.toBeInTheDocument()
  expect(document.documentElement).toHaveAttribute('data-theme', 'teal')
  expect(JSON.parse(requests.find(request => request.path === '/api/settings')!.init!.body as string)).toEqual({ theme: 'classic' })
})
