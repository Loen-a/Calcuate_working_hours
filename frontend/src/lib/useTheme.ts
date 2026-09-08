import { useLayoutEffect } from 'react'
import type { Theme } from './types'

export function useAppliedTheme(theme: Theme | null): void {
  useLayoutEffect(() => {
    if (theme === null) return
    const root = document.documentElement
    if (theme === 'cool') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
  }, [theme])
}
