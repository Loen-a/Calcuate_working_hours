# AGENTS.md

> **这个文件是给 AI 的"行为守则"（规则 + 约定），不是文档。** 详细业务规则 / 开发日志 / 踩过的坑 → `doc/`。

## ⚠️ 关键注意事项

1. **跨组件命名一致**：`frontend/src/App.tsx` 的 state 是 `viewY`/`viewM`，子组件 prop 是 `y`/`m`。**子组件永远用 prop 名**，不要用父 state 名（连踩两次坑后立的规矩）。
2. **build 必走 type-check**：`"build": "tsc --noEmit && vite build"`——缺 import / 未声明 var / 类型错 都在 build 拦下。复杂改动后建议在真浏览器手验一次（headless 还没配）。
3. **改文件前先 `Read`**：`Edit` 工具的 `old_string` 必须精确匹配（缩进、换行、import 行）。用 `grep -n` 定位后用**短而唯一**的锚点。
4. **主题切换**用 `data-theme` 属性 + CSS 变量覆盖（`[data-theme='xxx']` 块覆盖 `@theme` 的变量）。工具类名（`text-navy` / `bg-surface` 等）不动，业务零改动。`useLayoutEffect` 设属性，避免刷新闪一下。
5. **浏览器能力边界**：不能静默写指定目录、不能跨 origin 读 localStorage 等。**别在提需求前先问"能不能做"**——这是安全底线，不是技术细节。详见 `doc/backend/业务规则/数据存储与备份.md`。
6. **导出文件名要唯一**（`workhours-YYYY-MM-DD-HH-mm-ss.json`，精确到秒），否则浏览器加 ` (1)` ` (2)` 累积文件。

## 命名对照（prop vs state）

| 概念 | `frontend/src/App.tsx` state | 传给子组件的 prop |
|---|---|---|
| 查看的年 | `viewY` | `y` |
| 查看的月 | `viewM` | `m` |
| 节假日映射 | `hMap` | `hMap` |
| 所有打卡 | `entries` | `entries` |

## 详细文档

- `doc/CLAUDE.md` → doc/ 总规则（写哪、怎么写）
- `doc/frontend/业务规则/` → 前端业务逻辑（工时计算、推荐下班、推荐公式）
- `doc/frontend/项目日志/` → 前端开发过程（`YYYY-MM-DD-主题.md`）
- `doc/frontend/踩坑记录/` → 前端实际踩过的 bug：现象 / Root cause / 修复 / 怎么避免
- `doc/backend/` → 后端存储规则、设计规格、实施计划、项目日志和踩坑记录

## 跑

以下命令的当前目录都是**仓库根目录**：

- `npm --prefix frontend run dev` — 前端开发（`localhost:5173`）
- `poetry -C backend run pytest -v` — 后端测试

运行完整应用：

1. `npm --prefix frontend run build` — 执行 `tsc --noEmit && vite build`，生成 `frontend/dist/index.html`
2. `poetry -C backend run uvicorn backend.main:app --host 127.0.0.1 --port 8000`
3. 浏览器打开 `http://127.0.0.1:8000`

如果当前目录已经是 `backend/`：

- `npm --prefix ../frontend run dev` — 前端开发
- `npm --prefix ../frontend run build` — 前端 type-check + 构建
- `poetry run uvicorn backend.main:app --reload` — 后端开发服务（默认 `127.0.0.1:8000`）
- `poetry run pytest -v` — 后端测试
