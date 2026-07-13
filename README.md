# 工时统计 · Workhours

一个仅供本机单用户使用的工时统计应用。React 前端由 FastAPI 提供，工时记录、主题和节假日缓存统一保存在 SQLite 数据库 `backend/data/workhours.db`。使用时启动本地服务并访问 `http://127.0.0.1:8000`，不要双击构建产物。

## 技术栈

- **React 19** + **Vite** + **TypeScript**
- **Tailwind CSS v4**（`@tailwindcss/vite` 插件）
- **Recharts**（走势图）
- **vite-plugin-singlefile**（单文件产物）
- **FastAPI** + Python 内置 **sqlite3**（本地 API 与持久化）
- **Poetry**（项目内 Python 虚拟环境）
- **holiday-cn**（后端从 jsDelivr / GitHub Raw 获取并缓存，含调休）

## 功能

- **月历视图**（`Calendar`）：周一起头的月历网格，点日期打卡 / 编辑；周末/法定假日标"休"，调休上班日标"班"。
- **顶部推荐卡**（`Dashboard`）：标准 **08:00 → 推荐下班**（精确到分钟）。算法见下。
- **4 张统计卡**（`Dashboard`）：当月目标、已完成工时、盈余/缺口、工作日（已录入 / 本月工作日）。
- **走势图**（`TrendChart`）：当月累计盈余/缺口走势。
- **时间录入弹框**（`EntryModal` + `TimePicker`）：自定义冷调时间选择器（取代系统蓝白丑下拉）；周末 / 法定假日有「计入工时」开关（默认关），开了作为补时长计入。
- **补时长 30 分钟向下取整**（`floorTo30Min`）。
- **漏打卡提醒**（`App`）：当月已过去的 workday 中未打卡的日期，ochre 提示条。
- **时长统一格式** `X小时Y分钟`（分钟为 0 省略，hours 0 时只留"X分钟"）。
- **状态色**：盈余 navy / 缺口 plum / 加班 ochre / 周末 plum / 调休 navy / 无效 muted。
- **主题切换**（`Header` 右上「冷色 / 青绿」）：主题由后端 API 持久化到 SQLite；前端仍通过 `data-theme` 与 CSS 变量切换，业务组件不需要感知配色实现。
- **完整备份导出 / 导入**（`Header` 右上）：导出 version 2 JSON，包含 entries、主题与节假日缓存；导入同时兼容只迁移 entries 的旧版 version 1 JSON。

## 业务算法

### 工时 `calcNet(in, out)`
毛时长 − 与午休 `[12:00, 13:30]` 的重叠 − 与晚饭 `[19:30, 20:00]` 的重叠。

### 9 小时标准
`DAILY_TARGET = 9`。当月目标 = `9 × 当月工作日数`。

### 工作日
- 周一至周五 且 不在 `holiday-cn` 假日列表中 → workday
- `holiday-cn` 中 `isOffDay: true` → 假日（rest）
- `holiday-cn` 中 `isOffDay: false` → 调休上班（workday，即使在周末）

### 周末补时长（计入工时开关）
`counts === true` → 计入；`false` → 不计入；缺省时 workday 默认 `true`、rest day 默认 `false`。

计入的 rest day：净工时 `floorTo30Min`（半小时向下），**直接加入** `done`，**不**经 9h 扣减（所以"盈亏"对补时长是 +net，不是 net − 9）。

### 盈余 / 缺口
```
balance = done − 9 × (计入的 workday 天数)
```
`done` = workday 精确 net 之和 + rest day 取整后 net 之和。

### 推荐下班时间
- 目标日 = 今天（workday 且未打卡）/ 下一个 workday（已打卡 / 周末 / 假日）
- 剩余工作日 = 目标日（含）到月末的 workday 数
- `targetNet = 9 − balance / remaining`，clamp `[6h, 12h]`
- 下班 = `Math.round(8×60 + 90 + targetNet×60)` 分钟 → `HH:MM`

## 项目结构

```
frontend/
├── src/
│   ├── App.tsx              # 顶层 + state + 渲染 Dashboard / TrendChart / Calendar / Modal
│   ├── main.tsx             # 入口：createRoot + 挂载
│   ├── index.css            # Tailwind v4 + 设计 token（冷调调色板 + 字体）
│   ├── vite-env.d.ts        # 给 CSS import 补类型声明
│   ├── lib/
│   │   ├── types.ts         # WorkEntry / HolidayMap / DayInfo
│   │   ├── workHours.ts     # calcNet / fmtDuration / floorTo30Min / isEntryCounted
│   │   ├── holidays.ts      # dayInfo / workingDaysInMonth
│   │   ├── api.ts           # FastAPI 请求与备份上传/下载
│   │   ├── useCountUp.ts    # 数字补间 hook
│   │   ├── useMonthStats.ts # 当月统计共享 hook（Dashboard / 推荐卡复用）
│   │   └── useTheme.ts      # 将后端主题应用到 data-theme
│   └── components/
│       ├── Header.tsx       # 顶部 wordmark + 月份导航
│       ├── Dashboard.tsx    # 推荐卡 + 4 张统计卡
│       ├── TrendChart.tsx   # 累计盈余走势
│       ├── Calendar.tsx     # 月历
│       ├── EntryModal.tsx   # 录入弹框（含「计入工时」开关 + Net 预览）
│       └── TimePicker.tsx   # 自定义时间选择器（冷调 2 列滚轮）
├── index.html
└── package.json
backend/
├── backend/                 # FastAPI、API、services、repositories、SQLite 初始化
├── tests/                   # pytest 测试
├── data/                    # workhours.db 与手动下载的 JSON 备份
├── pyproject.toml
└── poetry.lock
doc/
├── frontend/                # 前端业务规则、项目日志和踩坑记录
└── backend/                 # 后端存储规则、设计规格、实施计划、项目日志和踩坑记录
```

## 安装、构建与运行

首次使用，在仓库根目录安装前后端依赖：

```bash
poetry -C backend install
npm --prefix frontend install
```

构建并启动：

```bash
npm --prefix frontend run build
poetry -C backend run uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

然后打开 `http://127.0.0.1:8000`。`build` 脚本会先执行 `tsc --noEmit`，再由 Vite 生成 `frontend/dist/index.html`；FastAPI 从固定的仓库路径提供该文件。如果页面返回 `503`，先重新执行构建命令。

开发前端时可另开终端执行 `npm --prefix frontend run dev`，Vite 地址为 `http://localhost:5173`。后端安装、启动和测试一律通过 Poetry；本项目**禁止使用全局 `pip install`**。

## 关键 prop / state 命名对照

| 概念 | `frontend/src/App.tsx` state | 传给子组件的 prop |
|---|---|---|
| 查看的年 | `viewY` | `y` |
| 查看的月 | `viewM` | `m` |
| 节假日映射 | `hMap` | `hMap` |
| 所有打卡 | `entries` | `entries` |

⚠️ 子组件里**永远**用 prop 名（`y` / `m`），**不要**用父组件 state 名（`viewY` / `viewM`）。本项目踩过这个坑两次，详见 `CLAUDE.md`。

## 设计 token

变量定义在 `frontend/src/index.css` 的 `@theme`，**所有业务组件通过工具类（`bg-paper` / `text-ink` / `border-rule` / `text-navy` 等）引用 `var(--color-*)`**——所以主题切换只需覆盖 CSS 变量，组件零改动。

### 冷色（默认）
- 背景 `paper` `#E4E6EA` · `surface` `#EEF0F3`
- 文字 `ink` `#15181C` · `ink-soft` `#5E646C`
- 边线 `rule` `#C5CACE`
- 盈余 `navy` `#2A4A6B` · 缺口 `plum` `#7A3A4E` · 加班 `ochre` `#8A6E1E`
- 字体：Display `Fraunces`（变体衬线，opsz+wght）· Body `Inter` · 数字 `JetBrains Mono` · 中文 `Noto Serif SC` / `Noto Sans SC`

### 淡雅青绿（`data-theme='teal'`）
- 背景 `paper` `#ECF2EF` · `surface` `#F4F8F6`
- 文字 `ink` `#1F2D2A` · `ink-soft` `#5A6B65`
- 边线 `rule` `#C8D4D0`
- 正 / 计入（替换 navy）`#2D6B5F` · 负 / rest（替换 plum）`#B36B5E` · 加班 ochre `#B0893D`
- 字体 sans：`"SF Pro Display", "PingFang SC", system-ui, -apple-system, sans-serif`

## 数据

- SQLite 文件：`backend/data/workhours.db`。
- 打卡、主题和节假日缓存都通过 `/api/*` 读写；浏览器 `localStorage` 不是正式数据源，后端不可用时也不会回退到浏览器存储。
- 顶栏 `导出` 下载 version 2 文件 `workhours-YYYY-MM-DD-HH-mm-ss.json`，可完整恢复 entries、主题和节假日缓存。
- 顶栏 `导入` 支持 version 2 完整恢复；旧版 version 1 仅替换 entries，不修改当前主题和节假日缓存。
- 网页不能静默指定下载目录；若希望手动备份默认落到 `backend/data/`，需在浏览器设置中修改下载位置。

详细的 API、事务和备份规则见 `doc/backend/业务规则/数据存储与备份.md`。
