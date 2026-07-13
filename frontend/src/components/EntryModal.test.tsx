import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import EntryModal from './EntryModal'

it('keeps the modal and input visible when the backend save fails', async () => {
  const onSave = vi.fn().mockRejectedValue(new Error('数据库写入失败'))
  const onClose = vi.fn()
  render(
    <EntryModal
      date="2026-07-12"
      entry={{ in: '08:00', out: '18:30', counts: true }}
      isRestDay={false}
      onClose={onClose}
      onSave={onSave}
      onDelete={vi.fn()}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: '保存' }))

  expect(await screen.findByText('数据库写入失败')).toBeInTheDocument()
  expect(screen.getByText('2026-07-12')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '上班 · In' })).toHaveTextContent('08:00')
  expect(screen.getByRole('button', { name: '下班 · Out' })).toHaveTextContent('18:30')
  expect(onClose).not.toHaveBeenCalled()
})

it('shows delete progress without relabeling the save button', async () => {
  const deleting = deferred<void>()
  render(
    <EntryModal
      date="2026-07-12"
      entry={{ in: '08:00', out: '18:30', counts: true }}
      isRestDay={false}
      onClose={vi.fn()}
      onSave={vi.fn()}
      onDelete={() => deleting.promise}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: '删除' }))

  expect(await screen.findByRole('button', { name: '删除中…' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '保存' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: '保存中…' })).not.toBeInTheDocument()

  deleting.resolve()
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}
