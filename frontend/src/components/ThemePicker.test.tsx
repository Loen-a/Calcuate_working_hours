import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import ThemePicker from './ThemePicker'

it('opens six options without cycling and closes the current choice without saving', async () => {
  const user = userEvent.setup(), select = vi.fn()
  render(<ThemePicker theme="cool" disabled={false} buttonClass="" onSelect={select} />)
  const trigger = screen.getByRole('button', { name: '冷色' })
  await user.click(trigger)
  expect(trigger).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getAllByRole('menuitemradio')).toHaveLength(6)
  expect(screen.getByRole('menuitemradio', { name: '冷色' })).toHaveAttribute('aria-checked', 'true')
  expect(select).not.toHaveBeenCalled()
  await user.click(screen.getByRole('menuitemradio', { name: '冷色' }))
  expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
  expect(select).not.toHaveBeenCalled()
})

it('selects exactly the clicked style and waits for the parent to apply it', async () => {
  const user = userEvent.setup(), select = vi.fn()
  const { rerender } = render(<ThemePicker theme="cool" disabled={false} buttonClass="" onSelect={select} />)
  await user.click(screen.getByRole('button', { name: '冷色' }))
  await user.click(screen.getByRole('menuitemradio', { name: '星际软糖' }))
  expect(select).toHaveBeenCalledExactlyOnceWith('space')
  expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '冷色' })).toBeInTheDocument()
  rerender(<ThemePicker theme="space" disabled={false} buttonClass="" onSelect={select} />)
  expect(screen.getByRole('button', { name: '星际软糖' })).toBeInTheDocument()
})

it('supports arrow navigation, Home/End, Escape and Enter without extra writes', async () => {
  const user = userEvent.setup(), select = vi.fn()
  render(<ThemePicker theme="classic" disabled={false} buttonClass="" onSelect={select} />)
  const trigger = screen.getByRole('button', { name: '经典绿' })
  trigger.focus()
  await user.keyboard('{ArrowDown}')
  expect(screen.getByRole('menuitemradio', { name: '经典绿' })).toHaveFocus()
  await user.keyboard('{End}')
  expect(screen.getByRole('menuitemradio', { name: '奶油手账' })).toHaveFocus()
  await user.keyboard('{ArrowDown}')
  expect(screen.getByRole('menuitemradio', { name: '冷色' })).toHaveFocus()
  await user.keyboard('{Home}{Escape}')
  expect(trigger).toHaveFocus()
  expect(select).not.toHaveBeenCalled()
  await user.keyboard('{ArrowDown}{End}{ArrowUp}{Enter}')
  expect(select).toHaveBeenCalledExactlyOnceWith('space')
  expect(trigger).toHaveFocus()
})

it('dismisses outside without taking focus away from the clicked control', async () => {
  const user = userEvent.setup(), select = vi.fn()
  render(<><ThemePicker theme="cool" disabled={false} buttonClass="" onSelect={select} /><button>其他操作</button></>)
  await user.click(screen.getByRole('button', { name: '冷色' }))
  await user.click(screen.getByRole('button', { name: '其他操作' }))
  expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '其他操作' })).toHaveFocus()
  expect(select).not.toHaveBeenCalled()
})

it('closes on Tab and continues to the next header control', async () => {
  const user = userEvent.setup()
  render(<><button>前一项</button><ThemePicker theme="cool" disabled={false} buttonClass="" onSelect={vi.fn()} /><button>后一项</button></>)
  await user.click(screen.getByRole('button', { name: '冷色' }))
  await user.tab()
  expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '后一项' })).toHaveFocus()
  await user.click(screen.getByRole('button', { name: '冷色' }))
  await user.tab({ shift: true })
  expect(screen.getByRole('button', { name: '前一项' })).toHaveFocus()
})

it('closes when the app becomes busy and prevents selection until it is ready', async () => {
  const user = userEvent.setup(), select = vi.fn()
  const { rerender } = render(<ThemePicker theme="cool" disabled={false} buttonClass="" onSelect={select} />)
  await user.click(screen.getByRole('button', { name: '冷色' }))
  rerender(<ThemePicker theme="cool" disabled buttonClass="" onSelect={select} />)
  expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '冷色' })).toBeDisabled()
  expect(select).not.toHaveBeenCalled()
})
