import { expect, it } from 'vitest'
import { fmtDate, shiftMonth } from './format'

it('preserves low years and clamps the selected day when navigating months', () => {
  expect(shiftMonth('0099-01-31', 1)).toBe('0099-02-28')
  expect(shiftMonth('0099-12-31', 1)).toBe('0100-01-31')
  expect(shiftMonth('0100-01-31', -1)).toBe('0099-12-31')
  expect(shiftMonth('0004-01-31', 1)).toBe('0004-02-29')
  expect(fmtDate(1, 1, 2)).toBe('0001-01-02')
})
