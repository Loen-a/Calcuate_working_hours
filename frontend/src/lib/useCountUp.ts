import { useEffect, useState } from 'react'

const prefersReduceMotion = () =>
  typeof window !== 'undefined' &&
  !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// 从当前显示值(val)出发动画到 target；首次入场从 0 出发；新 target 到达时若动画未完，
// 从当前可见值继续，不会回跳。
export function useCountUp(target: number, duration = 800): number {
  const [val, setVal] = useState(0)

  useEffect(() => {
    if (prefersReduceMotion()) {
      setVal(target)
      return
    }
    if (val === target) return
    const from = val
    const to = target
    const start = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const e = 1 - Math.pow(1 - t, 3) // easeOutCubic
      setVal(from + (to - from) * e)
      if (t < 1) {
        raf = requestAnimationFrame(tick)
      } else {
        setVal(to)
      }
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
    // val 是动画开始时的当前显示值（预期闭包），不是响应式依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, duration])

  return val
}
