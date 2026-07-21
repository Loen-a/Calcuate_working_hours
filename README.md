# Calculate Working Hours

用于记录弹性工时并按周平均或自然月平均预测每日建议工时的本地 Web 应用。

## 规则

- 目标平均工时为 9 小时，正常工作日最低建议 8 小时。
- 工作日由周一至周五、节假日和调休标记共同确定。
- 默认非工作时间为 12:00-13:30 和 19:30-20:00。
- 非工作时间可以新增、修改、启停或删除；只扣除与打卡时段的实际重叠部分，重叠规则不会重复扣除。
- 修改规则或历史打卡记录后，当前月份及所属周的预测会自动重算。
- 预测表按自然月记录相对每日 9 小时目标的累计余额，周视图会继承本月前序余额。

## 启动

安装依赖并前台启动：

    poetry install
    poetry run workhours-web

浏览器访问 http://127.0.0.1:5000。默认数据文件为项目目录下的 workhours.sqlite3。

隐藏 PowerShell 窗口后台启动：

    Start-Process -FilePath "poetry" -ArgumentList @("run", "workhours-web") -WorkingDirectory "D:\All_Software\Calculate_working_hours" -WindowStyle Hidden -RedirectStandardOutput "D:\All_Software\Calculate_working_hours\server.out.log" -RedirectStandardError "D:\All_Software\Calculate_working_hours\server.err.log"

停止服务：

    $webPid = (Get-NetTCPConnection -LocalPort 5000 -State Listen).OwningProcess
    Stop-Process -Id $webPid

## 测试

    poetry run pytest

