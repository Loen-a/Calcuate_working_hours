import { expect, it } from 'vitest'
import { fmtAverageHours, fmtDate, shiftMonth } from './format'

it.each([
  [510, '8.5'],
  [495, '8.25'],
  [540, '9'],
  [540.75, '9.01'],
  [487.5, '8.13'],
  [0, '0'],
  [null, '暂无数据'],
])('formats %s average minutes as decimal hours without trailing zeroes', (minutes, label) => {
  expect(fmtAverageHours(minutes)).toBe(label)
})

it('preserves low years and clamps the selected day when navigating months', () => {
  expect(shiftMonth('0099-01-31', 1)).toBe('0099-02-28')
  expect(shiftMonth('0099-12-31', 1)).toBe('0100-01-31')
  expect(shiftMonth('0100-01-31', -1)).toBe('0099-12-31')
  expect(shiftMonth('0004-01-31', 1)).toBe('0004-02-29')
  expect(fmtDate(1, 1, 2)).toBe('0001-01-02')
})
