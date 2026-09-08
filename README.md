# Calculate Working Hours

用于记录弹性工时并按周平均或自然月平均预测每日建议工时的本地 Web 应用。

默认打开新版界面（来自 `local-main` 的 React 布局），顶部按钮可切换新旧界面。选择会保存在当前浏览器中，正在查看的日期随切换保留。两套界面共用 Flask、同一个 SQLite 数据库和原主分支的 Python 工时计算。

新版 PC 界面在视口宽度达到 1024px 时，使用旧界面的 `Segoe UI / Microsoft YaHei` 字体及对应字号层级。桌面样式独立放在 `frontend/src/desktop.css`；小于 1024px 的手机和平板视口沿用原样式。

## 规则

- 目标平均工时为 9 小时，正常工作日最低建议 8 小时。
- 工作日由周一至周五、节假日和调休标记共同确定。
- 默认非工作时间为 12:00-13:30 和 19:30-20:00。
- 非工作时间可以新增、修改、启停或删除；只扣除与打卡时段的实际重叠部分，重叠规则不会重复扣除。
- 修改规则或历史打卡记录后，当前月份及所属周的预测会自动重算。
- 预测表按自然月记录相对每日 9 小时目标的累计余额，周视图会继承本月前序余额。
- 可只记录上班时间；下班时间早于上班时间时按次日计算。最早下班使用实际输入的上班时间、累计余额和已启用的非工作时段。
- 全天请假独立于打卡和日历标记保存。当天不计入目标、工时、余额、缺录提醒和下班预测；取消请假后原打卡和调休标记继续生效。本版仅支持全天请假。

## 节假日与调休

按查看年份从 [holiday-cn](https://github.com/NateScarlet/holiday-cn) 获取节假日和调休上班日期，并存入本地缓存。数据源依次为 jsDelivr 和 GitHub 原始文件；网络请求使用系统环境代理设置。

工作日判断顺序为：**手动日历标记 > 自动节假日/调休 > 周一至周五规则**，再从统计中排除请假日期。自动数据不会覆盖手动调整。

两套界面都提供“刷新节假日”。缓存不会自行过期；点击刷新会尝试获取上游修订，失败时保留已有缓存并提示。没有缓存且获取失败时暂按星期和手动标记计算。获取接口支持 2000–2100 年，但上游不保证每年都提供数据；范围外的日期仍可记录，使用星期和手动标记计算。

## 导入与导出

“导出”生成带唯一时间戳的 JSON 文件，包含全部打卡、统计周期、主题、自定义非工作时段、手动日历标记、请假日期和节假日缓存。浏览器的新旧界面选择属于本机偏好，不随备份转移。

**导入是覆盖恢复，建议先导出当前数据。** 选择文件并确认后，后端先校验整个文件，再以一个数据库事务恢复；格式错误或写入失败均保留原数据。最大文件大小为 16 MiB。

- 本版导出 `version: 3`，完整恢复所有业务类别。
- 兼容 `local-main` 的 v1/v2 JSON。v1 恢复打卡和请假；v2 还恢复主题和节假日缓存。旧备份未包含的主分支周期、休息时段和手动日历设置保持不变。
- 旧备份中非空 `counts`（单条记录是否参与工时）与主分支规则没有统一含义，因此整份导入会被拒绝并提示原因。请按主分支的日历规则确认记录后再迁移，不要直接删除字段来绕过提示。
- 旧请假记录两端均为 `00:00` 时转换为纯请假日期；只有一端为 `00:00` 时无法区分占位与真实午夜，导入会明确拒绝并指出日期。本版 v3 的真实午夜、跨日和仅上班记录均正常支持。
- 空年度节假日缓存会被拒绝，避免它阻止后续自动获取；没有任何缓存时顶层空 `holidayCache` 合法。

## 启动

Python 需要 3.11 或更新版本。安装依赖并前台启动：

    poetry install
    poetry run workhours-web

浏览器访问 http://127.0.0.1:5000。默认数据文件为项目目录下的 workhours.sqlite3。

仓库已包含新版界面的构建产物，正常运行只需上述 Python 服务，无需启动 Node、Vite 或 FastAPI。可用 `WORKHOURS_DB_PATH` 指定数据库文件路径；首次运行只新增请假和节假日缓存表，保留原有数据。

显式打开旧界面：`http://127.0.0.1:5000/?ui=old`；新版：`http://127.0.0.1:5000/?ui=new`。两个入口都会记住选择。

隐藏 PowerShell 窗口后台启动：

    Start-Process -FilePath "poetry" -ArgumentList @("run", "workhours-web") -WorkingDirectory "D:\All_Software\Calculate_working_hours" -WindowStyle Hidden -RedirectStandardOutput "D:\All_Software\Calculate_working_hours\server.out.log" -RedirectStandardError "D:\All_Software\Calculate_working_hours\server.err.log"

停止服务：

    $webPid = (Get-NetTCPConnection -LocalPort 5000 -State Listen).OwningProcess
    Stop-Process -Id $webPid

## 测试

    poetry run pytest

修改前端源码时使用 Node.js 22.12+（或兼容的更新版本）：

    npm --prefix frontend ci
    npm --prefix frontend test
    npm --prefix frontend run build

构建包含 TypeScript 检查，产物写入 `src/workhours/static/modern/index.html`，提交前端修改时需要一并更新。开发预览可运行 `npm --prefix frontend run dev`，其数据请求转发给 5000 端口的 Flask；完整的新旧界面切换请在 Flask 地址验收。

Python 测试使用临时数据库和可注入的节假日响应，不依赖真实网络。浏览器验收和联网获取应另行使用临时数据库验证。
