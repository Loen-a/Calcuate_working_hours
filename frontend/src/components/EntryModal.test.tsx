import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import EntryModal from './EntryModal'

it('keeps the modal and input visible when the backend save fails', async () => {
  const onSave = vi.fn().mockRejectedValue(new Error('数据库写入失败'))
  render(
    <EntryModal
      date="2026-07-12"
      entry={{ in: '08:00', out: '18:30', counts: true }}
      isRestDay={false}
      onClose={vi.fn()}
      onSave={onSave}
      onDelete={vi.fn()}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: '保存' }))

  expect(await screen.findByText('数据库写入失败')).toBeInTheDocument()
  expect(screen.getByText('2026-07-12')).toBeInTheDocument()
})
