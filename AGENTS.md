# AGENTS.md

> **这个文件是给 AI 的"行为守则"（规则 + 约定），不是文档。** 详细业务规则 / 开发日志 / 踩过的坑 → `doc/`。

## ⚠️ 关键注意事项

1. **跨组件命名一致**：`App.tsx` 的 state 是 `viewY`/`viewM`，子组件 prop 是 `y`/`m`。**子组件永远用 prop 名**，不要用父 state 名（连踩两次坑后立的规矩）。
2. **build 必走 type-check**：`"build": "tsc --noEmit && vite build"`——缺 import / 未声明 var / 类型错 都在 build 拦下。复杂改动后建议在真浏览器手验一次（headless 还没配）。
3. **改文件前先 `Read`**：`Edit` 工具的 `old_string` 必须精确匹配（缩进、换行、import 行）。用 `grep -n` 定位后用**短而唯一**的锚点。
4. **主题切换**用 `data-theme` 属性 + CSS 变量覆盖（`[data-theme='xxx']` 块覆盖 `@theme` 的变量）。工具类名（`text-navy` / `bg-surface` 等）不动，业务零改动。`useLayoutEffect` 设属性，避免刷新闪一下。
5. **浏览器能力边界**：不能静默写指定目录、不能跨 origin 读 localStorage 等。**别在提需求前先问"能不能做"**——这是安全底线，不是技术细节。详见 `doc/业务规则/数据存储与备份.md`。
6. **导出文件名要唯一**（`workhours-YYYY-MM-DD-HH-mm-ss.json`，精确到秒），否则浏览器加 ` (1)` ` (2)` 累积文件。

## 命名对照（prop vs state）

| 概念 | `App.tsx` state | 传给子组件的 prop |
|---|---|---|
| 查看的年 | `viewY` | `y` |
| 查看的月 | `viewM` | `m` |
| 节假日映射 | `hMap` | `hMap` |
| 所有打卡 | `entries` | `entries` |

## 详细文档

- `doc/CLAUDE.md` → doc/ 总规则（写哪、怎么写）
- `doc/业务规则/` → 定下来的业务逻辑（工时计算、推荐下班、推荐公式、数据存储与备份）
- `doc/项目日志/` → 按日期记的开发过程（`YYYY-MM-DD-主题.md`）
- `doc/踩坑记录/` → 实际踩过的 bug：现象 / Root cause / 修复 / 怎么避免

## 跑

- `npm run dev` — 开发（`localhost:5173`）
- `npm run build` — `tsc --noEmit && vite build` → `dist/index.html`（单文件，双击即开）
