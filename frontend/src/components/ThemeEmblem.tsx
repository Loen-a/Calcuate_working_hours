import type { Theme } from '../lib/types'

// 仅装饰品牌区域；日期、天气与业务状态继续使用原来的语义图标。
export default function ThemeEmblem({ theme }: { theme: Theme }) {
  if (theme === 'candy') return <svg className="workhours-theme-emblem" viewBox="0 0 40 40" aria-hidden="true">
    <circle cx="28" cy="11" r="7" fill="#FFD778" />
    <path d="M10 31h20a7 7 0 0 0 0-14 10 10 0 0 0-19-2A8 8 0 0 0 10 31Z" fill="#FFF" stroke="#4564D6" strokeWidth="2" />
    <circle cx="17" cy="23" r="1.2" fill="#324578" /><circle cx="25" cy="23" r="1.2" fill="#324578" />
    <path d="M19 27q2 2 4 0" fill="none" stroke="#D75E83" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
  if (theme === 'space') return <svg className="workhours-theme-emblem" viewBox="0 0 40 40" aria-hidden="true">
    <circle cx="20" cy="20" r="11" fill="#B5A5FF" />
    <path d="M5 27c-7-8 22-23 30-18s-14 23-29 20" fill="none" stroke="#75E2ED" strokeWidth="2.5" strokeLinecap="round" />
    <circle cx="16" cy="18" r="1.2" fill="#242B52" /><circle cx="23" cy="16" r="1.2" fill="#242B52" />
    <path d="m32 31 1.5 3 3 1.5-3 1.5-1.5 3-1.5-3-3-1.5 3-1.5Z" fill="#FFA6C9" />
  </svg>
  if (theme === 'journal') return <svg className="workhours-theme-emblem" viewBox="0 0 40 40" aria-hidden="true">
    <rect x="8" y="5" width="26" height="31" rx="4" fill="#FFFDF6" stroke="#47765F" strokeWidth="2" />
    <path d="M14 6v29M5 12h6M5 20h6M5 28h6" stroke="#47765F" strokeWidth="2" strokeLinecap="round" />
    <path d="M24 27s-8-5-6-9c2-3 5-1 6 1 1-2 4-4 6-1 2 4-6 9-6 9Z" fill="#E7AC8B" />
  </svg>
  return null
}
