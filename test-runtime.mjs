import { readFileSync } from 'node:fs'
import { JSDOM, VirtualConsole } from 'jsdom'
import vm from 'node:vm'

const html = readFileSync('dist/index.html', 'utf8')
const m = html.match(/<script type="module"[^>]*>([\s\S]*?)<\/script>/)
if (!m) { console.log('NO MODULE SCRIPT'); process.exit(2) }
const src = m[1]
console.log('script length:', src.length)

const errs = []
const vc = new VirtualConsole()
vc.on('jsdomError', (e) => errs.push(['jsdomError', e.message?.slice(0, 600), (e.stack || '').split('\n').slice(0, 8).join(' << ')]))
vc.on('error', (...a) => errs.push(['console.error', a.map(x => String(x).slice(0, 300)).join(' | ')]))

const dom = new JSDOM('<!DOCTYPE html><html><body><div id="root"></div></body></html>', {
  url: 'file:///app/',
  pretendToBeVisual: true,
  virtualConsole: vc,
  runScripts: 'outside-only',
})
dom.window.addEventListener('error', (e) => errs.push(['windowError', e.message, (e.error?.stack || '').split('\n').slice(0, 6).join(' << ')]))
dom.window.addEventListener('unhandledrejection', (e) => errs.push(['rejection', String(e.reason), (e.reason?.stack || '').split('\n').slice(0, 5).join(' << ')]))

const ctx = vm.createContext({})
// 显式把 JSDOM window 上的关键全局塞到 vm context 的 global 上
// （vm.createContext 不复制 prototype chain，所以 Window 上的 document/navigator 等 bare global 找不到）
const W = dom.window
const need = ['document', 'window', 'self', 'navigator', 'localStorage', 'sessionStorage',
             'fetch', 'AbortController', 'AbortSignal', 'URL', 'URLSearchParams',
             'console', 'queueMicrotask', 'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval',
             'Promise', 'Map', 'Set', 'WeakMap', 'WeakSet', 'Date', 'Math', 'JSON',
             'HTMLElement', 'HTMLDivElement', 'HTMLInputElement', 'HTMLButtonElement',
             'Node', 'Element', 'Event', 'CustomEvent', 'MouseEvent', 'KeyboardEvent',
             'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame',
             'addEventListener', 'removeEventListener', 'crypto']
for (const k of need) {
  try { if (k in W) ctx[k] = W[k] } catch {}
}
// React 17+ / 某些库用 IS_REACT_ACT_ENVIRONMENT
ctx.IS_REACT_ACT_ENVIRONMENT = true
ctx.React = await import('react').catch(() => null)  // not needed for bundled React

const mod = new vm.SourceTextModule(src, { identifier: 'app.js' })
try {
  await mod.link(async (spec) => { throw new Error('UNEXPECTED IMPORT: ' + spec) })
} catch (e) {
  errs.push(['LINK_THROW', e.message])
  console.log('LINK FAILED:', e.message); process.exit(1)
}

try {
  await mod.evaluate({ context: ctx })
} catch (e) {
  errs.push(['EVAL_THROW', e.message?.slice(0, 600), (e.stack || '').split('\n').slice(0, 10).join(' << ')])
}

await new Promise(r => setTimeout(r, 3000))

const root = dom.window.document.getElementById('root')
const inner = root?.innerHTML ?? ''
const text = root?.textContent ?? ''

console.log('\n===== ERRORS (' + errs.length + ') =====')
for (const e of errs) {
  console.log(' ', e[0], '|', e[1])
  if (e[2]) console.log('    stack:', e[2])
}

console.log('\n===== ROOT =====')
console.log('  innerHTML len:', inner.length)
console.log('  text len:', text.length)
console.log('  text first 200:', text.slice(0, 200).replace(/\n/g, ' '))
console.log('  has 工时:', text.includes('工时'))
console.log('  has 08:00:', text.includes('08:00'))
console.log('  has 推荐上下班:', text.includes('推荐上下班'))

const fatal = errs.length > 0
console.log('\n===== RESULT =====')
console.log(fatal ? 'FAIL — 真有运行时错误' : (inner.length > 100 ? 'PASS — React 挂载成功，root 有内容' : 'root 空但无错（可能 effects 还没跑完）'))
process.exit(fatal ? 1 : 0)
