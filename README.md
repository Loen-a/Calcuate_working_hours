# 工时记录：手机端归档

本分支 `archive/mobile` 保存从 `feat/desktop-workspace` 的 `2646fb7` 提取的现有手机版本，**暂停功能更新**。PC 端继续在 `main` 和 `feat/desktop-workspace` 维护；以后恢复手机开发时从本分支继续，按需选择公共业务修复。

保留手机日历（点击日期直接编辑、六周视图）、下班预测、冷色/青绿主题，以及旧版手机界面切换。新版窗口变宽仍保持手机日历和交互。导入的经典绿设置保留在数据库中，本界面显示冷色；只有用户主动切换主题才写入新选择。

工时计算、全天请假、节假日/调休、非工作时段和 JSON 导入导出继续由同一套 Python 后端提供。数据文件格式兼容 PC 分支，使用既有数据库时不会删除记录。PC 专用的详情侧栏、天气、湿度和 AQI 不在这个冻结版本中。

## 运行

需要 Python 3.11+。在本分支目录执行：

```sh
poetry install
poetry run workhours-web
```

访问 http://127.0.0.1:5000 ，默认数据库为 `workhours.sqlite3`，可通过 `WORKHOURS_DB_PATH` 指定。新版入口 `/?ui=new`，旧版入口 `/?ui=old`。

## 验证与构建

```sh
poetry run pytest
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
```

前端使用 Node.js 22.12+。仓库附带 `src/workhours/static/modern/index.html` 构建产物，正常启动只需 Python 服务。手机版本保留必要的公共后端；日常 PC 更新不会自动同步到这个分支。
