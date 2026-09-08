import { useLayoutEffect, useSyncExternalStore } from 'react'
import type { Theme } from './types'

export function useAppliedTheme(theme: Theme | null): void {
  useLayoutEffect(() => {
    if (theme === null) return
    const root = document.documentElement
    if (theme === 'cool') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
  }, [theme])
}


const desktopQuery = '(min-width: 1024px)'
function subscribeDesktopChange(onChange: () => void): () => void {
  const media = window.matchMedia(desktopQuery)
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}
const isDesktop = () => window.matchMedia(desktopQuery).matches

export function useDesktopViewport(): boolean {
  return useSyncExternalStore(subscribeDesktopChange, isDesktop)
}
