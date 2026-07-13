# Windows 一键启动与进程联动设计

## 1. 目标

为本机 Windows 单用户提供一个可双击的启动入口。首次运行时自动补齐项目依赖，之后每次启动重新构建前端、启动 FastAPI，并在服务健康后打开普通的独立浏览器窗口。用户关闭该专用窗口后，启动器必须停止本次创建的 Uvicorn 进程。

## 2. 范围

本次新增两个文件：

- `start-workhours.cmd`：仓库根目录的双击入口。
- `scripts/start-workhours.ps1`：依赖检查、构建、进程启动、健康检查和清理逻辑。

同时更新根 `README.md` 的安装与启动说明。`scripts/` 只保存跨前后端的运行编排，不放前端或后端业务代码；前端源码仍只在 `frontend/`，后端源码和 Python 环境仍只在 `backend/`，详细文档仍按 `doc/frontend/` 与 `doc/backend/` 分开。

本次不新增系统服务、托盘程序、前端心跳、后端 shutdown API 或全局依赖，也不改变节假日请求的无代理行为。

## 3. 方案选择

采用 `.cmd` 薄入口和 PowerShell 生命周期脚本的两层方案。

- 单个 `.cmd` 适合双击，但不适合可靠保存 PID、轮询 HTTP 和执行 `finally` 清理。
- 单个 `.ps1` 易受 Windows PowerShell 执行策略影响，不适合作为直接双击入口。
- `.cmd` 使用当前进程级 `-ExecutionPolicy Bypass` 调用 `.ps1`，兼顾双击体验和进程管理能力，不修改系统执行策略。

## 4. 启动流程

`start-workhours.cmd` 使用 `%~dp0` 切换到仓库根目录，然后调用：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-workhours.ps1
```

PowerShell 脚本按顺序执行：

1. 将工作目录固定为脚本推导出的仓库根目录，不依赖用户从哪个目录双击。
2. 检查 `poetry`、`npm` 和可用浏览器。浏览器优先使用 Microsoft Edge，找不到时回退到 Google Chrome。
3. 检查 `127.0.0.1:8000` 是否已有监听者。若端口被占用，立即失败，不复用或终止未知进程。
4. 若 `backend/.venv/Scripts/python.exe` 不存在，执行 `poetry -C backend install`。该命令只使用 `backend/.venv`，不调用全局 `pip install`。
5. 若 `frontend/node_modules` 不存在，执行 `npm --prefix frontend install`。
6. 每次执行 `npm --prefix frontend run build`，确保 FastAPI 提供的 `frontend/dist/index.html` 与当前源码一致。
7. 通过 `poetry -C backend run uvicorn backend.main:app --host 127.0.0.1 --port 8000` 创建新的服务进程并保存其 PID。
8. 轮询 `http://127.0.0.1:8000/api/health`。只有收到成功响应才打开浏览器；达到超时时间或服务提前退出则失败并清理。

每个外部命令都检查退出码。`.cmd` 只在 PowerShell 返回失败时显示提示并 `pause`，正常关闭时不要求额外按键。

## 5. 浏览器与服务生命周期

启动器为浏览器创建位于系统临时目录下的唯一 profile，并使用以下参数打开带地址栏和标签栏的普通独立窗口：

```text
--new-window
http://127.0.0.1:8000
--user-data-dir=<unique-temp-profile>
--no-first-run
--no-default-browser-check
--disable-background-mode
--disable-extensions
--disable-sync
```

独立 profile 防止 Edge 或 Chrome 把窗口交给用户已经打开的普通浏览器进程。该临时 profile 禁用扩展和同步，避免每次新建 profile 时重新同步 Adblock Plus 等扩展、打开扩展安装页或显示同步提醒；这些参数只作用于临时窗口，不修改用户日常 Edge/Chrome profile 的扩展、账号、书签或设置。

浏览器参数由独立的 `Get-WorkhoursBrowserArguments` 函数生成，以便原生 PowerShell 测试精确验证：包含普通窗口 URL、禁用扩展和禁用同步参数，同时不再包含任何 `--app=` 参数。

PowerShell 保存新浏览器主进程的 PID，并等待该进程退出。关闭专用普通窗口后，该 profile 的浏览器主进程应退出，等待随即结束。

所有已启动资源都由同一个 `try/finally` 管理：

- 若启动器创建了 Uvicorn，则只针对保存的服务 PID 终止该进程树；不得按进程名批量终止 Python、Poetry、Edge 或 Chrome。
- 若启动器创建了临时浏览器 profile，则在确认浏览器退出后，只删除本次生成且位于系统临时目录下的目录。
- 启动失败、健康检查失败、浏览器启动失败和正常关闭浏览器都经过相同清理路径。

“关闭浏览器后停止进程”特指关闭启动器打开的专用普通窗口。脚本不尝试监控用户日常浏览器中的任意标签页。

## 6. 错误处理

错误信息必须指出失败阶段和可执行的修复方向：

- 缺少 Poetry：提示安装 Poetry 并确认 `poetry` 在 PATH 中。
- 缺少 npm：提示安装 Node.js/npm 并确认 `npm` 在 PATH 中。
- 未找到 Edge/Chrome：提示安装任一受支持浏览器。
- 端口 8000 被占用：提示先关闭占用者，不自动杀进程。
- 依赖安装或前端构建失败：保留原命令输出并退出。
- 服务提前退出或健康检查超时：停止本次服务进程树并退出。

错误处理不修改全局代理、Python、npm 或 PowerShell 配置。

## 7. README 更新

README 增加“一键启动”小节，说明：

- 双击 `start-workhours.cmd` 即可启动。
- 首次运行会自动安装项目内依赖，之后仍会每次构建前端。
- 服务健康后出现普通的独立浏览器窗口；该窗口不加载用户扩展或同步用户资料。
- 关闭该窗口会自动停止本次 Uvicorn 服务。
- 命令行手动启动方式继续保留，便于开发和排错。

## 8. 验证

实现完成后执行：

1. PowerShell 语法解析和批处理入口检查。
2. 原生 PowerShell 测试确认浏览器参数包含 `--new-window`、应用 URL、`--disable-extensions` 和 `--disable-sync`，且不包含 `--app=`。
3. 在现有依赖环境运行启动器，确认 `/api/health` 返回成功且普通浏览器主窗口直接显示工时页面。
4. 可视检查该专用窗口没有 Adblock Plus 安装页、同步提醒或额外欢迎标签。
5. 通过窗口的正常关闭操作结束专用浏览器，确认启动器退出且 8000 端口释放。
6. 确认临时 profile 和专用浏览器进程已清理，用户已有浏览器进程未被终止。
7. 运行后端完整测试、前端测试、前端构建和 `git diff --check`。
8. 确认工作树只包含启动脚本、原生测试、README 和本设计对应的必要变更。
