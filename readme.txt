poetry install
poetry run workhours-web

cd D:\All_Software\Calculate_working_hours
http://127.0.0.1:5000/

Start-Process -FilePath "poetry" `
  -ArgumentList @("run", "workhours-web") `
  -WorkingDirectory "D:\All_Software\Calculate_working_hours" `
  -WindowStyle Hidden `
  -RedirectStandardOutput "D:\All_Software\Calculate_working_hours\server.out.log" `
  -RedirectStandardError "D:\All_Software\Calculate_working_hours\server.err.log"


$webPid = (Get-NetTCPConnection -LocalPort 5000 -State Listen).OwningProcess
Stop-Process -Id $webPid