# 本地后端与数据库持久化设计

日期：2026-07-12  
状态：已通过对话及书面规格复核

## 1. 目标

为现有工时统计前端增加一个仅供本机单用户使用的后端。FastAPI 同时提供前端页面和 API，SQLite 成为工时记录、主题偏好和节假日缓存的唯一持久化来源。

完成后，用户通过 `http://127.0.0.1:8000` 使用应用，不再依赖浏览器 `localStorage` 保存正式数据。开发开始前先将现有前端整理到 `frontend/`，后端全部放入 `backend/`，两者的源码、依赖、测试、数据和文档不得混放。

## 2. 第一版范围

第一版包含：

- 使用 Python、FastAPI 和 Python 内置 `sqlite3`。
- 使用项目独立的 Poetry 虚拟环境管理 Python 版本和依赖，不向全局 Python 环境安装包。
- FastAPI 提供构建后的 `frontend/dist/index.html` 和 `/api/*` 接口。
- SQLite 文件位于 `backend/data/workhours.db`。
- 每个日期最多保存一条工时记录。
- 数据库保存工时记录、主题偏好和按年份缓存的节假日数据。
- 后端从 `holiday-cn` 获取节假日数据并负责缓存。
- 支持旧版工时 JSON 迁移和新版完整备份的导入、导出。
- 现有净工时、月度统计、走势图和推荐下班时间算法继续留在前端。

第一版不包含：

- 多用户、注册、登录和权限系统。
- 局域网或公网访问。
- 一天多段上下班记录。
- 离线编辑、双向同步或 `localStorage` 兜底。
- 将净工时、盈亏、月度统计等派生结果写入数据库。
- 独立数据库服务、ORM 或 Alembic。

## 3. 架构

```text
浏览器
  │  http://127.0.0.1:8000
  ▼
FastAPI
  ├─ 提供 frontend/dist/index.html 和静态资源
  ├─ 提供 /api/*
  ├─ 获取 holiday-cn 节假日数据
  └─ 调用 repository
          │
          ▼
   backend/data/workhours.db
```

后端默认只监听 `127.0.0.1`。因为它不向局域网或公网开放，第一版不增加鉴权。

生产使用时，FastAPI 提供 Vite 构建产物和 API。开发时可以分别启动 Vite 与 FastAPI；后端仅允许本机 Vite 开发地址 `http://localhost:5173` 和 `http://127.0.0.1:5173` 跨域访问。

### 3.1 模块边界

- `backend.main`：创建 FastAPI 应用、初始化数据库、注册 API 路由、提供 `frontend/dist/index.html`。
- `schemas`：定义 API 请求和响应模型，完成日期、时间、主题及备份结构校验。
- `repositories`：集中保存 SQL，提供工时、偏好和节假日缓存的数据库操作。
- `services`：编排节假日获取、完整备份导出和事务性导入。
- `db`：创建短生命周期连接、初始化表结构并管理 `PRAGMA user_version`。

API 路由不直接编写 SQL。Repository 不依赖 FastAPI 请求或响应对象，因此可以使用临时数据库独立测试。

### 3.2 仓库目录边界

```text
frontend/
  src/
  index.html
  package.json
  package-lock.json
  vite.config.ts
  tsconfig.json
  dist/

backend/
  backend/
  tests/
  data/
  pyproject.toml
  poetry.lock
  poetry.toml
  .venv/

doc/
  frontend/
  backend/
```

- 前端源码、npm 依赖和前端测试只放在 `frontend/`。
- FastAPI 源码、Poetry 依赖、后端测试、SQLite 和 JSON 备份只放在 `backend/`。
- 前端业务规则、项目日志和踩坑记录放入 `doc/frontend/`。
- 后端的存储规则、设计规格、实施计划、项目日志和踩坑记录放入 `doc/backend/`。
- 根目录只保留 `AGENTS.md`、`CLAUDE.md`、`README.md` 等共享入口文件。
- 整理目录是后端实现的第一个任务，完成并验证前端仍能构建后，才能创建后端代码。

### 3.3 Python 环境与依赖管理

- 使用 Poetry 管理后端依赖，`pyproject.toml`、`poetry.lock` 和 `poetry.toml` 均位于 `backend/`。
- 将 Poetry 配置为项目内虚拟环境，使用 `backend/.venv`，并把它加入根 `.gitignore`。
- 从仓库根目录使用 `poetry -C backend install` 安装依赖，不执行全局 `pip install`。
- 后端启动、测试及其他 Python 命令统一通过 `poetry -C backend run` 执行。
- FastAPI 应用入口固定为 `backend/backend/main.py` 中的 `app`，从仓库根目录启动时使用 `poetry -C backend run uvicorn backend.main:app --host 127.0.0.1 --port 8000`。

## 4. SQLite 数据结构

数据库使用 SQLite 自带的 `PRAGMA user_version` 记录 schema 版本。第一版版本号为 `1`。

### 4.1 `work_entries`

```sql
CREATE TABLE work_entries (
    work_date  TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time   TEXT NOT NULL,
    counts     INTEGER NULL CHECK (counts IN (0, 1) OR counts IS NULL)
);
```

- `work_date` 使用有效 ISO 日期 `YYYY-MM-DD`。
- `start_time` 和 `end_time` 使用有效的 24 小时制 `HH:MM`。
- `end_time` 必须晚于 `start_time`，不支持跨天打卡。
- `counts = 1` 表示计入，`0` 表示不计入，`NULL` 表示沿用工作日默认计入、休息日默认不计入的现有规则。
- 保存同一天使用 upsert；日期主键保证一天至多一条记录。

数据库保存原始输入，不保存净工时、加班时长或盈亏结果。

### 4.2 `preferences`

```sql
CREATE TABLE preferences (
    id    INTEGER PRIMARY KEY CHECK (id = 1),
    theme TEXT NOT NULL CHECK (theme IN ('cool', 'teal'))
);
```

初始化数据库时插入 `id = 1, theme = 'cool'`。更新主题只修改这一行。

### 4.3 `holiday_cache`

```sql
CREATE TABLE holiday_cache (
    year         INTEGER PRIMARY KEY,
    payload_json TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);
```

- `payload_json` 保存该年份完整的 `HolidayMap` JSON。
- `fetched_at` 保存最近成功获取的 UTC ISO 时间。
- 按年整包保存，因为应用只会整年获取和替换节假日映射，不需要 SQL 级日期查询。
- 外部获取失败的空结果不得写入缓存。

## 5. API 设计

除文件下载外，API 使用 JSON。错误响应统一使用 FastAPI 的 `{ "detail": "..." }` 结构。

### 5.1 健康检查

#### `GET /api/health`

用于确认服务和数据库连接正常。

成功响应：

```json
{
  "status": "ok"
}
```

### 5.2 工时记录

#### `GET /api/entries`

返回全部记录，直接兼容前端现有 `Entries` 结构：

```json
{
  "2026-07-12": {
    "in": "08:00",
    "out": "18:30",
    "counts": true
  }
}
```

若数据库中的 `counts` 为 `NULL`，响应可以省略 `counts`，保持现有可选字段语义。

#### `PUT /api/entries/{date}`

请求：

```json
{
  "in": "08:00",
  "out": "18:30",
  "counts": true
}
```

校验通过后新增或覆盖该日期，返回保存后的日期和记录。路径日期与正文记录不存在两个来源，正文中不重复传日期。

#### `DELETE /api/entries/{date}`

删除成功返回 `204 No Content`；记录不存在返回 `404`。

### 5.3 主题偏好

#### `GET /api/preferences`

```json
{
  "theme": "cool"
}
```

#### `PUT /api/preferences`

请求和成功响应都使用：

```json
{
  "theme": "teal"
}
```

只接受 `cool` 或 `teal`。

### 5.4 节假日

#### `GET /api/holidays/{year}`

响应：

```json
{
  "year": 2026,
  "holidays": {
    "01-01": {
      "name": "元旦",
      "isOffDay": true
    }
  },
  "source": "cache"
}
```

`source` 取值：

- `cache`：从 SQLite 缓存读取。
- `remote`：本次从外部获取成功，并已写入 SQLite。
- `fallback`：缓存不存在且两个外部地址都失败，`holidays` 为空映射。

处理顺序：

1. 命中对应年份缓存时直接返回，不访问外部网络。
2. 未命中时先请求 jsDelivr，再请求 GitHub Raw。
3. 成功结果写入数据库并返回。
4. 全部失败时返回 `fallback`，前端按周末推断并显示提示；失败结果不入库。

### 5.5 完整备份

#### `GET /api/backup`

返回 version 2 JSON 文件，并设置精确到秒的唯一文件名：

```text
workhours-YYYY-MM-DD-HH-mm-ss.json
```

备份结构：

```json
{
  "version": 2,
  "exportedAt": "2026-07-12T12:00:00.000Z",
  "entries": {},
  "preferences": {
    "theme": "cool"
  },
  "holidayCache": {
    "2026": {
      "holidays": {},
      "fetchedAt": "2026-01-01T00:00:00.000Z"
    }
  }
}
```

#### `POST /api/backup`

使用 multipart 文件上传。后端完整读取、解析和校验后才开始修改数据库。

兼容规则：

- version 1：现有 `{ version, exportedAt, entries }` 格式；只替换 `work_entries`，保留当前主题和节假日缓存。
- version 2：替换工时、主题和节假日缓存三类数据。

version 2 导入在单个事务中完成。任何字段不合法或任何写入失败时全部回滚。成功响应返回导入版本和各类数据数量，前端随后重新加载全部状态。

## 6. 前端改造边界与数据流

增加独立 API 适配层，React 组件不直接拼接 URL 或调用 `localStorage`。

### 6.1 启动

应用启动时并行请求：

```text
GET /api/entries
GET /api/preferences
GET /api/holidays/{当前年份}
```

在主题和主要数据尚未加载完成前显示初始化状态，避免先使用默认主题绘制再闪烁。数据加载完成后，再向 Dashboard、TrendChart 和 Calendar 传递现有 `entries`、`hMap`、`y`、`m` props。

切换年份时仅重新请求目标年份节假日数据。工时计算、月度统计、趋势和推荐下班时间继续使用当前前端函数，不迁移到后端。

### 6.2 写入

- 保存记录：等待 `PUT /api/entries/{date}` 成功后更新 `entries` state 并关闭弹框。
- 删除记录：等待 `DELETE` 成功后从 state 删除并关闭弹框。
- 切换主题：等待 `PUT /api/preferences` 成功后应用新主题。
- 写入期间禁用重复提交。
- 写入失败时保留用户输入和原 state，显示可重试错误。

第一版使用服务端确认后的更新，不采用乐观更新和失败回滚。

### 6.3 存储替换

- 工时记录不再读写 `localStorage['workhours_v1']`。
- 主题不再读写 `localStorage['workhours_theme_v1']`。
- 节假日不再读写 `localStorage['holidaycn_v1_<year>']`，也不再由前端直接访问外部 CDN。
- 后端不可用时不回退到浏览器存储，以免产生两个数据源。
- 现有导入、导出按钮保留，但改为调用后端完整备份 API。

## 7. 错误处理与一致性

### 7.1 API 状态码

- `400 Bad Request`：备份版本或整体文件结构不合法。
- `404 Not Found`：删除的工时记录不存在。
- `422 Unprocessable Entity`：日期、时间、主题或记录字段校验失败。
- `500 Internal Server Error`：未预期的数据库或后端错误。
- `503 Service Unavailable`：必须依赖的服务暂时不可用。

节假日外部数据源失败不返回 `503`，因为系统已有明确的周末推断降级方案；此时返回成功响应和 `source = fallback`。

后端日志保留异常类型和定位信息，但 API 不返回 SQL、数据库路径或堆栈。

### 7.2 数据库一致性

- 应用启动时初始化数据库和缺失表；初始化失败则应用启动失败。
- 每次请求使用短生命周期 SQLite 连接。
- 连接启用外键检查和合理的 busy timeout。
- 完整备份导入使用显式事务。
- API 返回写入成功后，前端才更新对应 state。

## 8. 测试设计

后端使用 `pytest`，并从仓库根目录通过 `poetry -C backend run pytest` 执行。每个测试使用独立临时 SQLite 数据库，不读写真实 `backend/data/workhours.db`。

### 8.1 Repository 测试

- 新增、读取、覆盖和删除工时记录。
- 日期主键保证同一天只有一条记录。
- `counts` 的 `true`、`false` 和缺省语义正确往返。
- 默认主题为 `cool`，并可更新为 `teal`。
- 节假日缓存可以按年份保存、读取和覆盖。
- 关闭并重新打开连接后数据仍存在。

### 8.2 API 测试

- 合法工时记录 CRUD。
- 非法日期、非法时间、下班不晚于上班和非法主题被拒绝。
- 删除不存在记录返回 `404`。
- 数据库异常转换为统一错误响应。
- 健康检查能够验证数据库连接。

### 8.3 节假日服务测试

- 缓存命中时不访问网络。
- 缓存缺失时按顺序尝试两个来源。
- 成功获取后写入缓存。
- 两个来源都失败时返回 `fallback`，且不缓存空结果。
- 测试使用模拟 HTTP 响应，不依赖真实互联网。

### 8.4 备份测试

- version 1 只替换工时数据。
- version 2 在一个事务中替换全部三类数据。
- 非法备份和中途写入失败均不会改变原有数据。
- 完整导出、清空、导入后可以恢复相同状态。

### 8.5 前端验证

- API 适配层覆盖成功响应、API 错误和网络中断。
- `npm --prefix frontend run build` 必须通过 `tsc --noEmit` 和 Vite 构建。
- 在真实浏览器中手动验证一次完整流程。

## 9. 验收标准

以下条件全部满足才算第一版完成：

1. `frontend/`、`backend/`、`doc/frontend/` 和 `doc/backend/` 边界清楚，不存在前后端源码、依赖或测试混放。
2. 构建前端并启动 FastAPI 后，可以通过 `http://127.0.0.1:8000` 打开应用。
3. 空数据库首次启动时自动建表，并使用默认主题 `cool`。
4. 新增、编辑和删除工时记录后刷新页面，结果与数据库一致。
5. 停止并重启后端后，工时、主题和节假日缓存仍然存在。
6. 浏览器 `localStorage` 不保存上述三类正式数据。
7. 现有 version 1 JSON 可以将历史工时记录迁移进数据库，且不覆盖当前主题和节假日缓存。
8. version 2 完整备份能够导出并事务性恢复全部三类状态。
9. 后端不可用或保存失败时，前端显示错误且不产生本地副本。
10. 节假日获取失败时页面仍可使用，并明确提示按周末推断。
11. `poetry -C backend run pytest` 和 `npm --prefix frontend run build` 均通过，并完成真实浏览器手验。
12. 后端依赖只存在于 `backend/.venv` 中，全局 Python 环境未被安装或修改。
