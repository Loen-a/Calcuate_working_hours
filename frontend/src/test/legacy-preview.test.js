import { expect, it, vi } from 'vitest'
import { waitFor } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), '../src/workhours/static/app.js'), 'utf8')

it('keeps full-day leave guidance when editing preserved punches or clearing the start', async () => {
  document.body.innerHTML = `
    <section id="selected-forecast" data-preview-url="/preview/earliest-end" data-selected-leave="1"></section>
    <span id="selected-balance"></span><span id="selected-preview-copy"></span>
    <span id="selected-reason"></span><span id="selected-required"></span>
    <span id="selected-preview-status">全天请假</span><span id="selected-earliest-end"></span>
    <input data-preview-start data-preview-scope="selected" data-preview-target="selected-earliest-end" data-work-date="2026-09-08" value="08:00">
  `
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ available: false }))))
  window.eval(source)
  const input = document.querySelector('input')
  input.dispatchEvent(new Event('change'))
  await waitFor(() => expect(document.querySelector('#selected-preview-copy')).toHaveTextContent('取消请假'))
  expect(document.querySelector('#selected-preview-status')).toHaveTextContent('全天请假')
  input.value = ''
  input.dispatchEvent(new Event('change'))
  expect(document.querySelector('#selected-preview-status')).toHaveTextContent('全天请假')
})
