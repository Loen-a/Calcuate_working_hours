import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(cleanup)

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: () => ({
    matches: true,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }),
})

class ResizeObserverStub {
  constructor(_callback: ResizeObserverCallback) {}
  observe(_target: Element) {}
  unobserve(_target: Element) {}
  disconnect() {}
}

globalThis.ResizeObserver = ResizeObserverStub as typeof ResizeObserver
