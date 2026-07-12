# 工时统计 · Workhours

一个个人工作小时统计工具，单页面 Web 应用。数据存本地浏览器（`localStorage`），无需后端，产物为单个 HTML 文件（`frontend/dist/index.html` ≈ 590 KB），双击即可打开。

## 技术栈

- **React 19** + **Vite** + **TypeScript**
- **Tailwind CSS v4**（`@tailwindcss/vite` 插件）
- **Recharts**（走势图）
- **vite-plugin-singlefile**（单文件产物）
- **holiday-cn**（法定节假日数据，jsDelivr / raw.githubusercontent CDN 拉取，含调休）

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
- **主题切换**（`Header` 右上「冷色 / 青绿」）：默认冷调，可切到「淡雅青绿」配色（背景 celadon 绿、计入/盈余 `#2D6B5F`、缺口/休息 淡珊瑚 `#B36B5E`、加班 金棕 `#B0893D`、正文 `SF Pro Display` + 中文 `PingFang SC`）。选择持久化 `localStorage['workhours_theme_v1']`。实现：`data-theme` 属性 + CSS 变量覆盖，**业务组件零改动**。
- **手动导出 / 导入**（`Header` 右上）：导出 = 下载 `workhours-YYYY-MM-DD-HH-mm-ss.json`；导入 = 选 JSON 覆盖当前 entries（有数据时先 `confirm`）。浏览器**不能**静默写到指定目录——把 Chrome 下载位置改到项目下 `backend/data/` 文件夹可以"默认落盘"。详见 `doc/backend/业务规则/数据存储与备份.md`。

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
│   │   ├── holidays.ts      # fetchHolidays / dayInfo / workingDaysInMonth
│   │   ├── storage.ts       # localStorage 读写
│   │   ├── useCountUp.ts    # 数字补间 hook
│   │   ├── useMonthStats.ts # 当月统计共享 hook（Dashboard / 推荐卡复用）
│   │   ├── useTheme.ts      # 主题切换 hook（data-theme + localStorage 持久化）
│   │   └── backup.ts        # 导出 / 导入 JSON 工具（buildExport / parseImport / downloadExport）
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
└── data/                    # 现有 JSON 备份；后端代码尚未创建
doc/
├── frontend/                # 前端业务规则、项目日志和踩坑记录
└── backend/                 # 后端存储规则、设计规格、实施计划、项目日志和踩坑记录
```

## 跑

```bash
npm --prefix frontend install
npm --prefix frontend run dev      # 开发：localhost:5173，热更新
npm --prefix frontend run build    # 产物：frontend/dist/index.html（双击即开）
```

`build` 脚本是 `tsc --noEmit && vite build`：tsc 先做类型检查，vite 再 bundle。改源码如果 import 漏了或类型错了，**build 阶段就报错**，不会溜到浏览器运行时。

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

- 打卡：`localStorage` key `workhours_v1`
  - 每条 entry 形如 `{ in: "08:00", out: "18:00", counts?: boolean }`
- 节假日缓存：`holidaycn_v1_<year>`
- 主题：`workhours_theme_v1`（`'cool'` | `'teal'`）

**数据存浏览器、不在文件夹里**——`frontend/dist/index.html` 双击打开时，localStorage 按 `file://` 路径 + 浏览器 profile 锁。**挪文件夹、换浏览器、清除浏览数据都会丢**。所以加了手动备份：

- 顶栏 `导出` → 下载 `workhours-YYYY-MM-DD-HH-mm-ss.json`（建议存到项目下 `backend/data/` 文件夹）
- 顶栏 `导入` → 选 JSON 覆盖当前 entries（有数据先 `confirm`）
- 浏览器**不能**让网页静默写到指定目录——想把"默认到 backend/data/"，在 Chrome 设置 → 下载 → 位置改到 `backend/data/` 文件夹（一次性）。详见 `doc/backend/业务规则/数据存储与备份.md`。
