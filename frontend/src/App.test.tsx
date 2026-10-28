import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'

const date = '2026-09-08'
const makeDashboard = () => ({
  today: date, selected_date: date, theme: 'teal',
  settings: { period: 'month', target_minutes_per_day: 540, minimum_minutes_per_day: 480,
    earliest_start_time: null as string | null, earliest_end_time: null as string | null },
  intervals: [{ interval_id: 1, name: '午休', start_time: '12:00', end_time: '13:00', enabled: true }],
  days: Array.from({ length: 30 }, (_, i) => ({
    date: `2026-09-${String(i + 1).padStart(2, '0')}`, is_workday: true, leave: false,
    calendar_name: '工作日', manual_override: null,
    entry: i === 7 ? { start_time: '10:13', end_time: null as string | null } : null,
    actual_minutes: null as number | null, daily_balance_minutes: null, cumulative_balance_minutes: null,
    balance_before_minutes: -37, required_minutes: 577, recommended_minutes: 600,
    suggested_end: '21:17', suggested_end_day_offset: 0, reason: 'balance', compliant: null as boolean | null, before_earliest_end: false,
  })),
  selected_preview: { available: true, required_minutes: 577, required_label: '9 小时 37 分钟',
    balance_before_minutes: -37, balance_label: '-37 分钟', reason_label: '补足历史欠时',
    suggested_end: '21:17', suggested_end_label: '21:17', day_offset: 0 },
  averages: { all_time_minutes: 510 as number | null, month_minutes: 501 as number | null },
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
let afterPunch: (() => void) | undefined
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
  afterPunch = undefined
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
    if (path === '/api/weather') return json({
      city: '杭州', timezone: 'Asia/Shanghai', month: new URL(input, window.location.origin).searchParams.get('month'),
      forecast_start: '2026-09-08', forecast_end: '2026-09-14', source: 'cache', stale: false,
      fetched_at: '2026-09-08T00:00:00+00:00', warning: null, days: {},
    })
    if (path === '/api/air-quality') return json({
      city: '杭州', timezone: 'Asia/Shanghai', standard: 'US', month: new URL(input, window.location.origin).searchParams.get('month'),
      forecast_start: '2026-09-08', forecast_end: '2026-09-14', source: 'cache', stale: false,
      fetched_at: '2026-09-08T00:00:00Z', warning: null, days: {},
    })
    if (path === '/api/settings' && init?.method === 'PUT') {
      if (settingsError) return json({ error: settingsError }, 400)
      const settings = JSON.parse(init.body as string)
      if (settings.theme) dashboard.theme = settings.theme
      for (const key of ['earliest_start_time', 'earliest_end_time'] as const) {
        if (key in settings) dashboard.settings[key] = settings[key]
      }
      return json({ ok: true })
    }
    if (path === '/preview/earliest-end') return json(dashboard.selected_preview)
    if (path === '/api/backup' && init?.method === 'POST') {
      return importError ? json({ error: importError }, 400) : json({ version: 3, entries: 1 })
    }
    if (path.startsWith('/api/entries/') && entryError) return json({ error: entryError }, 400)
    if (path.startsWith('/api/entries/') && init?.method === 'PUT') {
      afterPunch?.()
      return json({ ok: true })
    }
    if (path === '/api/clock-out' || path === '/api/clock-in') {
      afterPunch?.()
      return json({ date })
    }
    // Allow the original interface to render so red exposes its client-side calculation.
    if (path === '/api/entries') return json({})
    if (path === '/api/preferences') return json({ theme: 'teal' })
    if (path === '/api/holidays/2026') return json({ year: 2026, holidays: {}, source: 'cache' })
    return json({ ok: true })
  }))
})

it('uses the server prediction and monthly totals, and preserves the selected date in the interface switch', async () => {
  mockDesktopViewport(true)
  render(<App />)
  expect(await screen.findByText('21:17')).toBeInTheDocument()
  expect(screen.getByText('189h')).toBeInTheDocument()
  expect(screen.getByText('25h 03m')).toBeInTheDocument()
  const averages = screen.getByText('平均用时').parentElement!
  expect(within(averages).getByText('8.35/8.5')).toBeInTheDocument()
  expect(within(averages).getByText('月平均/总平均')).toBeInTheDocument()
  expect(averages).not.toHaveTextContent('小时/天')
  expect(averages).not.toHaveTextContent('已完成')
  expect(screen.getByRole('link', { name: '切换旧界面' })).toHaveAttribute('href', `/interface/old?reference_date=${date}`)
  expect(document.documentElement).toHaveAttribute('data-theme', 'teal')
  await openDateEditor('2026-09-09')
  await screen.findByRole('dialog')
  expect(screen.getByRole('link', { name: '切换旧界面' })).toHaveAttribute('href', '/interface/old?reference_date=2026-09-09')
  expect(screen.getByText('平均用时').parentElement).toHaveTextContent('8.35/8.5')
})

it('shows no average data when there are no valid recorded days', async () => {
  dashboard.averages = { all_time_minutes: null, month_minutes: null }
  render(<App />)
  const averages = (await screen.findByText('平均用时')).parentElement!
  expect(within(averages).getByText('暂无数据')).toBeInTheDocument()
})

it('saves a start-only record without inventing an end time', async () => {
  mockDesktopViewport(true)
  render(<App />)
  await openDateEditor(date)
  await screen.findByRole('dialog')
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '保存打卡' }))
  await waitFor(() => expect(requests.some(r => r.path === `/api/entries/${date}`)).toBe(true))
  const saved = requests.find(r => r.path === `/api/entries/${date}`)!
  expect(JSON.parse(saved.init!.body as string)).toEqual({ start_time: '10:13', end_time: null })
})

it('saves cross-midnight punches and retains inputs when saving fails', async () => {
  mockDesktopViewport(true)
  dashboard.days[7].entry = { start_time: '22:10', end_time: '07:40' }
  entryError = '数据库写入失败'
  render(<App />)
  await openDateEditor(date)
  await screen.findByRole('dialog')
  fireEvent.click(screen.getByRole('button', { name: '保存打卡' }))
  expect(await screen.findByText('数据库写入失败')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '上班 · In' })).toHaveTextContent('22:10')
  expect(screen.getByRole('button', { name: '下班 · Out' })).toHaveTextContent('07:40')
  expect(JSON.parse(requests.find(r => r.path === `/api/entries/${date}`)!.init!.body as string))
    .toEqual({ start_time: '22:10', end_time: '07:40' })
  expect(window.alert).not.toHaveBeenCalled()
})

it.each([
  { minutes: 390, compliant: false, warning: '净工时为 6.5 小时，不足 8 小时，还差 1h 30m。' },
  { minutes: 479, compliant: false, warning: '净工时为 7.98 小时，不足 8 小时，还差 1m。' },
  { minutes: 0, compliant: false, warning: '净工时为 0 小时，不足 8 小时，还差 8h。' },
  { minutes: 480, compliant: true, warning: '' },
  { minutes: 481, compliant: true, warning: '' },
  { minutes: null, compliant: null, warning: '' },
])('uses refreshed server compliance after saving ($minutes minutes)', async ({ minutes, compliant, warning }) => {
  // The result must come from the refresh, not from the previously displayed record.
  dashboard.days[7].actual_minutes = 200
  dashboard.days[7].compliant = false
  afterPunch = () => {
    dashboard.days[7].actual_minutes = minutes
    dashboard.days[7].compliant = compliant
  }
  render(<App />)
  await openDateEditor(date)
  fireEvent.click(await screen.findByRole('button', { name: '保存打卡' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  if (warning) {
    expect(window.alert).toHaveBeenCalledExactlyOnceWith(`${date} 打卡记录已保存。\n${warning}`)
  } else {
    expect(window.alert).not.toHaveBeenCalled()
  }
  expect(requests.filter(r => r.path === `/api/entries/${date}` && r.init?.method === 'PUT')).toHaveLength(1)
})

it('warns for the clock-out date even when viewing a different date', async () => {
  window.history.replaceState({}, '', '/?reference_date=2026-09-09')
  afterPunch = () => {
    dashboard.days[7].actual_minutes = 390
    dashboard.days[7].compliant = false
  }
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '现在下班' }))
  expect(await screen.findByRole('status')).toHaveTextContent('已记录当前下班时间')
  expect(screen.getByLabelText('查看日期')).toHaveValue(date)
  expect(window.alert).toHaveBeenCalledExactlyOnceWith(`${date} 打卡记录已保存。\n净工时为 6.5 小时，不足 8 小时，还差 1h 30m。`)
})

it('does not warn on clock-in even when a saved record is below the minimum', async () => {
  dashboard.days[7].actual_minutes = 390
  dashboard.days[7].compliant = false
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '现在上班' }))
  expect(await screen.findByRole('status')).toHaveTextContent('已记录当前上班时间')
  expect(window.alert).not.toHaveBeenCalled()
})

it.each(['save', 'clock-out'])('warns on an early departure even with eight net hours (%s)', async action => {
  dashboard.settings.earliest_end_time = '17:00'
  afterPunch = () => {
    dashboard.days[7].actual_minutes = 480
    dashboard.days[7].compliant = true
    dashboard.days[7].before_earliest_end = true
  }
  render(<App />)
  if (action === 'save') {
    await openDateEditor(date)
    fireEvent.click(await screen.findByRole('button', { name: '保存打卡' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  } else {
    fireEvent.click(await screen.findByRole('button', { name: '现在下班' }))
    await screen.findByRole('status')
  }
  expect(window.alert).toHaveBeenCalledExactlyOnceWith(`${date} 打卡记录已保存。\n实际下班时间早于设定的最早下班打卡时间 17:00。`)
})

it('combines short-hours and early-departure warnings in one dialog', async () => {
  dashboard.settings.earliest_end_time = '17:00'
  afterPunch = () => {
    dashboard.days[7].actual_minutes = 390
    dashboard.days[7].compliant = false
    dashboard.days[7].before_earliest_end = true
  }
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '现在下班' }))
  await screen.findByRole('status')
  expect(window.alert).toHaveBeenCalledTimes(1)
  expect(vi.mocked(window.alert).mock.calls[0][0]).toContain('不足 8 小时')
  expect(vi.mocked(window.alert).mock.calls[0][0]).toContain('最早下班打卡时间 17:00')
})

it('saves nullable clock limits and clears each limit independently', async () => {
  render(<App />)
  fireEvent.click(await screen.findByText('统计周期、打卡限制与非工作时段'))
  const start = screen.getByLabelText('最早上班打卡时间')
  const end = screen.getByLabelText('最早下班打卡时间')
  expect(start).toHaveValue('')
  expect(end).toHaveValue('')
  fireEvent.change(start, { target: { value: '08:30' } })
  fireEvent.change(end, { target: { value: '17:00' } })
  fireEvent.click(screen.getByRole('button', { name: '保存打卡时间限制' }))
  await screen.findByText('打卡时间限制已保存')
  expect(dashboard.settings.earliest_start_time).toBe('08:30')
  expect(dashboard.settings.earliest_end_time).toBe('17:00')
  fireEvent.click(screen.getByRole('button', { name: '清空最早上班打卡时间' }))
  fireEvent.click(screen.getByRole('button', { name: '保存打卡时间限制' }))
  await waitFor(() => expect(dashboard.settings.earliest_start_time).toBeNull())
  await waitFor(() => expect(screen.getByRole('button', { name: '保存打卡时间限制' })).toBeEnabled())
  expect(end).toHaveValue('17:00')
  fireEvent.click(screen.getByRole('button', { name: '清空最早下班打卡时间' }))
  fireEvent.click(screen.getByRole('button', { name: '保存打卡时间限制' }))
  await waitFor(() => expect(dashboard.settings.earliest_end_time).toBeNull())
  expect(requests.filter(r => r.path === '/api/settings').map(r => JSON.parse(r.init!.body as string))).toEqual([
    { earliest_start_time: '08:30', earliest_end_time: '17:00' },
    { earliest_start_time: null, earliest_end_time: '17:00' },
    { earliest_start_time: null, earliest_end_time: null },
  ])
})

it('preserves edited limits and saved settings when saving fails', async () => {
  dashboard.settings.earliest_end_time = '17:00'
  settingsError = '设置保存失败'
  render(<App />)
  fireEvent.click(await screen.findByText('统计周期、打卡限制与非工作时段'))
  fireEvent.change(screen.getByLabelText('最早下班打卡时间'), { target: { value: '18:00' } })
  fireEvent.click(screen.getByRole('button', { name: '保存打卡时间限制' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('设置保存失败')
  expect(screen.getByLabelText('最早下班打卡时间')).toHaveValue('18:00')
  expect(dashboard.settings.earliest_end_time).toBe('17:00')
  expect(screen.getByRole('button', { name: '保存打卡时间限制' })).toBeEnabled()
})

it('reports a failed post-save refresh without issuing an unverified minimum-hours warning', async () => {
  dashboard.days[7].actual_minutes = 390
  dashboard.days[7].compliant = false
  afterPunch = () => { dashboardError = '刷新失败' }
  render(<App />)
  await openDateEditor(date)
  fireEvent.click(await screen.findByRole('button', { name: '保存打卡' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('操作已完成，但重新读取失败')
  expect(window.alert).not.toHaveBeenCalled()
})

it('sets leave independently without overwriting preserved punches', async () => {
  mockDesktopViewport(true)
  render(<App />)
  await openDateEditor(date)
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
  expect(screen.getByRole('button', { name: `选择 ${date}` })).toBeDisabled()
  expect(screen.getByRole('button', { name: '编辑所选日期' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '编辑所选日期' }))
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

it('saves the chosen style through the menu without cycling on the trigger', async () => {
  mockDesktopViewport(true)
  dashboard.theme = 'cool'
  render(<App />)
  let previous = '冷色'
  const choices = [['candy', '晴空糖果'], ['space', '星际软糖'], ['journal', '奶油手账'], ['teal', '青绿'], ['classic', '经典绿'], ['cool', '冷色']]
  for (const [id, label] of choices) {
    const count = requests.filter(request => request.path === '/api/settings').length
    fireEvent.click(await screen.findByRole('button', { name: previous }))
    expect(requests.filter(request => request.path === '/api/settings')).toHaveLength(count)
    fireEvent.click(screen.getByRole('menuitemradio', { name: label }))
    expect(await screen.findByRole('button', { name: label })).toBeInTheDocument()
    expect(dashboard.theme).toBe(id)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    previous = label
  }
  expect(requests.filter(request => request.path === '/api/settings').map(request => JSON.parse(request.init!.body as string).theme))
    .toEqual(choices.map(([id]) => id))
})



it('keeps the previous theme visible when saving classic theme fails', async () => {
  mockDesktopViewport(true)
  settingsError = '主题保存失败，请重试'
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: '青绿' }))
  fireEvent.click(screen.getByRole('menuitemradio', { name: '经典绿' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('主题保存失败，请重试')
  expect(screen.getByRole('button', { name: '青绿' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '经典绿' })).not.toBeInTheDocument()
  expect(document.documentElement).toHaveAttribute('data-theme', 'teal')
  expect(JSON.parse(requests.find(request => request.path === '/api/settings')!.init!.body as string)).toEqual({ theme: 'classic' })
})

it('selects a PC calendar date into the detail panel before explicitly opening the editor', async () => {
  mockDesktopViewport(true)
  render(<App />)
  const panel = await screen.findByRole('complementary', { name: '所选日期详情' })
  expect(within(panel).getByRole('heading', { name: date })).toBeInTheDocument()
  expect(within(panel).getByText('21:17')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '选择 2026-09-09' }))
  await waitFor(() => expect(within(panel).getByRole('heading', { name: '2026-09-09' })).toBeInTheDocument())
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(requests.some(request => request.init?.method === 'PUT')).toBe(false)
  fireEvent.click(within(panel).getByRole('button', { name: '编辑所选日期' }))
  expect(await screen.findByRole('dialog')).toHaveTextContent('2026-09-09')
})

it('keeps the previous selected date and details when PC navigation fails', async () => {
  mockDesktopViewport(true)
  render(<App />)
  const panel = await screen.findByRole('complementary', { name: '所选日期详情' })
  dashboardError = '读取所选日期失败'
  fireEvent.click(screen.getByRole('button', { name: '选择 2026-09-09' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('读取所选日期失败')
  expect(within(panel).getByRole('heading', { name: date })).toBeInTheDocument()
  expect(screen.getByLabelText('查看日期')).toHaveValue(date)
  expect(screen.getByRole('button', { name: `选择 ${date}` })).toHaveAttribute('aria-pressed', 'true')
})



it.each(['pending', 'failed'])('keeps PC date selection, editing and saving usable while weather is %s', async mode => {
  mockDesktopViewport(true)
  const originalFetch = vi.mocked(fetch).getMockImplementation()!
  const weatherCalls: RequestInit[] = []
  vi.mocked(fetch).mockImplementation((input, init) => {
    if (String(input).startsWith('/api/weather?')) {
      weatherCalls.push(init || {})
      return mode === 'pending' ? new Promise<Response>(() => undefined) : Promise.reject(new Error('天气连接失败'))
    }
    return originalFetch(input, init)
  })
  render(<App />)
  expect(await screen.findByText(mode === 'pending' ? '天气加载中…' : '天气暂不可用，稍后自动重试')).toBeInTheDocument()
  const selected = screen.getByRole('button', { name: `选择 ${date}` })
  expect(selected).toBeEnabled()
  fireEvent.click(selected)
  await waitFor(() => expect(selected).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: '编辑所选日期' }))
  fireEvent.click(await screen.findByRole('button', { name: '保存打卡' }))
  await waitFor(() => expect(requests.some(request => request.path === `/api/entries/${date}` && request.init?.method === 'PUT')).toBe(true))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(weatherCalls).toHaveLength(1)
  expect(screen.getByRole('button', { name: `选择 ${date}` })).toBeEnabled()
})


async function openDateEditor(value: string) {
  const cell = await screen.findByRole('button', { name: `选择 ${value}` })
  await waitFor(() => expect(cell).toBeEnabled())
  fireEvent.click(cell)
  await waitFor(() => expect(screen.getByLabelText('查看日期')).toHaveValue(value))
  await waitFor(() => expect(screen.getByRole('button', { name: '编辑所选日期' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: '编辑所选日期' }))
  await screen.findByRole('dialog')
}

it('keeps the PC workspace, classic theme and weather when the viewport is narrow', async () => {
  const resize = mockDesktopViewport(false)
  dashboard.theme = 'classic'
  render(<App />)
  expect(await screen.findByRole('button', { name: '经典绿' })).toBeInTheDocument()
  expect(screen.getByRole('complementary', { name: '所选日期详情' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: `选择 ${date}` })).toBeInTheDocument()
  expect(requests.some(request => request.path === '/api/weather')).toBe(true)
  expect(requests.some(request => request.path === '/api/air-quality')).toBe(true)
  await act(async () => resize(true))
  await act(async () => resize(false))
  expect(screen.getByRole('button', { name: '经典绿' })).toBeInTheDocument()
  expect(requests.some(request => request.path === '/api/settings')).toBe(false)
})
