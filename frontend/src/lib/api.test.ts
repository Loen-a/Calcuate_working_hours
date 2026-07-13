import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getEntries, putEntry } from './api'

describe('api adapter', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('returns entries from the backend', async () => {
    const entries = {
      '2026-07-12': { in: '08:00', out: '18:30', counts: true },
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(entries), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    await expect(getEntries()).resolves.toEqual(entries)
  })

  it('unwraps a saved entry', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          date: '2026-07-12',
          entry: { in: '08:00', out: '18:30', counts: true },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    await expect(
      putEntry('2026-07-12', {
        in: '08:00',
        out: '18:30',
        counts: true,
      }),
    ).resolves.toEqual({ in: '08:00', out: '18:30', counts: true })
  })

  it('exposes backend error detail and status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'database operation failed' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    await expect(getEntries()).rejects.toEqual(
      new ApiError(500, 'database operation failed'),
    )
  })
})
