import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './lib/api'

vi.mock('./lib/api')

beforeEach(() => {
  vi.mocked(api.getEntries).mockResolvedValue({})
  vi.mocked(api.getPreferences).mockResolvedValue({ theme: 'teal' })
  vi.mocked(api.getHolidays).mockResolvedValue({
    year: new Date().getFullYear(),
    holidays: {},
    source: 'cache',
  })
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
