import { useLayoutEffect, useState } from 'react'

export type Theme = 'cool' | 'teal'
const KEY = 'workhours_theme_v1'

function getInitial(): Theme {
  try {
    return (localStorage.getItem(KEY) as Theme) || 'cool'
  } catch {
    return 'cool'
  }
}

// 把主题写到 <html data-theme="...">，CSS 变量覆盖由此触发。
// 用 useLayoutEffect 在浏览器首次绘制前同步设上，避免刷新闪一下。
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(getInitial)
  useLayoutEffect(() => {
    const root = document.documentElement
    if (theme === 'cool') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      /* ignore */
    }
  }, [theme])
  const toggle = () => setTheme((t) => (t === 'cool' ? 'teal' : 'cool'))
  return [theme, toggle]
}
