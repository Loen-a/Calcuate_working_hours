import type { Entries } from './types'

const VERSION = 1

export interface ExportPayload {
  version: number
  exportedAt: string
  entries: Entries
}

// 从 localStorage 读出当前所有打卡，组装成导出包
export function buildExport(): ExportPayload {
  let entries: Entries = {}
  try {
    entries = JSON.parse(localStorage.getItem('workhours_v1') || '{}')
  } catch {
    /* ignore */
  }
  return {
    version: VERSION,
    exportedAt: new Date().toISOString(),
    entries,
  }
}

// 解析导入文件，校验基本结构
export function parseImport(text: string): Entries {
  const data = JSON.parse(text)
  if (
    !data ||
    typeof data !== 'object' ||
    !data.entries ||
    typeof data.entries !== 'object' ||
    Array.isArray(data.entries)
  ) {
    throw new Error('文件格式不对：缺少 entries 字段')
  }
  for (const [, v] of Object.entries(data.entries)) {
    if (!v || typeof (v as { in?: unknown }).in !== 'string' || typeof (v as { out?: unknown }).out !== 'string') {
      throw new Error('文件格式不对：有 entry 缺 in/out')
    }
  }
  return data.entries as Entries
}

// 触发浏览器下载（保存位置/文件名由浏览器/用户决定）
export function downloadExport(): void {
  const payload = buildExport()
  const text = JSON.stringify(payload, null, 2)
  const blob = new Blob([text], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const date = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  a.href = url
  a.download = `workhours-${date}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
