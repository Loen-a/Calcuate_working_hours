# Windows One-Click Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Windows launcher that installs missing project-local dependencies, rebuilds the frontend, opens the app in a dedicated browser window, and stops its Uvicorn process when that window closes.

**Architecture:** A root `start-workhours.cmd` provides the double-click entry point and invokes a PowerShell lifecycle manager without changing the machine execution policy. `scripts/start-workhours.ps1` owns tool discovery, dependency checks, the frontend build, the exact Uvicorn process tree, a unique Edge/Chrome profile, health polling, and cleanup through one `try/finally` boundary.

**Tech Stack:** Windows CMD, Windows PowerShell 5.1-compatible syntax, Poetry, npm, Uvicorn, Microsoft Edge or Google Chrome, native PowerShell assertions for tests.

## Global Constraints

- Keep frontend source and dependencies under `frontend/`; keep backend source, tests, data, Poetry metadata, and `.venv` under `backend/`.
- Use `poetry -C backend install` and `poetry -C backend run`; never call global `pip install`.
- Keep the root `scripts/` directory limited to cross-component launch orchestration and its tests; do not move business logic there.
- Do not add a shutdown API, frontend heartbeat, system service, tray application, third-party PowerShell module, or new application dependency.
- Do not read or modify global proxy, Python, npm, browser, or PowerShell configuration.
- Do not reuse or terminate an unknown listener on `127.0.0.1:8000`.
- Only terminate PIDs created and recorded by this launcher. Never kill Python, Poetry, Edge, or Chrome by process name.
- The browser window must use a unique profile under the system temporary directory so it does not reuse the user's existing browser process.
- Preserve the holiday service's `trust_env=False` behavior.
- `start-workhours.cmd` pauses only on failure; normal browser-window closure exits without an additional prompt.

---

## File Structure

- Create `scripts/start-workhours.ps1` — all launcher functions and the PowerShell entry point.
- Create `scripts/tests/start-workhours.tests.ps1` — dependency-free unit checks for path resolution, browser selection, TCP listener detection, and safe temporary-profile cleanup.
- Create `start-workhours.cmd` — double-click wrapper that fixes the working directory and reports PowerShell failures.
- Modify `README.md` — add the one-click workflow while retaining manual install/start commands.

### Task 1: PowerShell lifecycle manager

**Files:**
- Create: `scripts/tests/start-workhours.tests.ps1`
- Create: `scripts/start-workhours.ps1`

**Interfaces:**
- Consumes: repository layout (`backend/`, `frontend/`), `poetry`, `npm`, `taskkill.exe`, Edge or Chrome, `GET /api/health` returning `{ "status": "ok" }`.
- Produces: `Invoke-WorkhoursLauncher()` as the lifecycle entry point; pure helpers `Resolve-FirstExistingPath`, `Get-WorkhoursBrowserPath`, `Test-WorkhoursTcpPort`, `Wait-WorkhoursHealth`, `Remove-WorkhoursTemporaryProfile`, and `Stop-WorkhoursProcessTree`.

- [ ] **Step 1: Write the native PowerShell test file before the production script exists**

Create `scripts/tests/start-workhours.tests.ps1`:

```powershell
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'start-workhours.ps1'
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Launcher script does not exist: $scriptPath"
}

. $scriptPath

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Expected, $Actual, [string]$Message)
    if ($Expected -ne $Actual) {
        throw "$Message Expected: $Expected Actual: $Actual"
    }
}

$tempFile = New-TemporaryFile
$listener = $null
$profileDir = $null

try {
    $missing = Join-Path ([System.IO.Path]::GetTempPath()) 'workhours-missing-browser.exe'
    $resolved = Resolve-FirstExistingPath -Candidates @($missing, $tempFile.FullName)
    Assert-Equal $tempFile.FullName $resolved 'First existing path was not selected.'

    $browser = Get-WorkhoursBrowserPath -Candidates @($missing, $tempFile.FullName)
    Assert-Equal $tempFile.FullName $browser 'Browser fallback order was not respected.'

    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    Assert-True (Test-WorkhoursTcpPort -Port $port) 'Listening port was not detected.'
    $listener.Stop()
    $listener = $null
    Assert-True (-not (Test-WorkhoursTcpPort -Port $port)) 'Released port stayed busy.'

    $profileDir = Join-Path (
        [System.IO.Path]::GetTempPath()
    ) ("worktime-statistics-browser-test-{0}" -f [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $profileDir | Out-Null
    Set-Content -LiteralPath (Join-Path $profileDir 'marker.txt') -Value 'test'
    Remove-WorkhoursTemporaryProfile -ProfilePath $profileDir
    Assert-True (-not (Test-Path -LiteralPath $profileDir)) 'Temporary profile was not removed.'
    $profileDir = $null

    Write-Host 'PowerShell launcher unit tests passed.' -ForegroundColor Green
} finally {
    if ($listener) { $listener.Stop() }
    if ($profileDir -and (Test-Path -LiteralPath $profileDir)) {
        Remove-Item -LiteralPath $profileDir -Recurse -Force
    }
    Remove-Item -LiteralPath $tempFile.FullName -Force -ErrorAction SilentlyContinue
}
```

- [ ] **Step 2: Run the test and verify the expected RED failure**

Run from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/tests/start-workhours.tests.ps1
```

Expected: non-zero exit with `Launcher script does not exist` because `scripts/start-workhours.ps1` has not been created.

- [ ] **Step 3: Implement the minimal lifecycle manager**

Create `scripts/start-workhours.ps1`:

```powershell
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-FirstExistingPath {
    param([Parameter(Mandatory)][string[]]$Candidates)

    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return [System.IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}

function Get-WorkhoursBrowserPath {
    param([string[]]$Candidates)

    if (-not $Candidates) {
        $Candidates = @(
            (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
            (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
            (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\Application\msedge.exe'),
            (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
            (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
            (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
        )
    }

    $browser = Resolve-FirstExistingPath -Candidates $Candidates
    if (-not $browser) {
        throw 'Microsoft Edge or Google Chrome was not found. Install one supported browser.'
    }
    return $browser
}

function Get-RequiredCommandPath {
    param([Parameter(Mandatory)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command '$Name' was not found in PATH."
    }
    return $command.Source
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList,
        [Parameter(Mandatory)][string]$Stage
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$Stage failed with exit code $LASTEXITCODE."
    }
}

function Test-WorkhoursTcpPort {
    param([Parameter(Mandatory)][int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $result = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $result.AsyncWaitHandle.WaitOne(250)) { return $false }
        $client.EndConnect($result)
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-WorkhoursHealth {
    param(
        [Parameter(Mandatory)][System.Diagnostics.Process]$ServerProcess,
        [int]$TimeoutSeconds = 30
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($ServerProcess.HasExited) {
            throw "Uvicorn exited before becoming healthy (exit code $($ServerProcess.ExitCode))."
        }
        try {
            $response = Invoke-RestMethod `
                -Uri 'http://127.0.0.1:8000/api/health' `
                -TimeoutSec 2
            if ($response.status -eq 'ok') { return }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    throw 'Timed out waiting for http://127.0.0.1:8000/api/health.'
}

function Stop-WorkhoursProcessTree {
    param([System.Diagnostics.Process]$Process)

    if (-not $Process -or $Process.HasExited) { return }
    & taskkill.exe /PID $Process.Id /T /F | Out-Null
}

function Remove-WorkhoursTemporaryProfile {
    param([string]$ProfilePath)

    if (-not $ProfilePath) { return }
    $fullPath = [System.IO.Path]::GetFullPath($ProfilePath)
    $tempRoot = [System.IO.Path]::GetFullPath(
        [System.IO.Path]::GetTempPath()
    ).TrimEnd('\') + '\'
    $leaf = Split-Path -Leaf $fullPath
    if (
        -not $fullPath.StartsWith(
            $tempRoot,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -or
        -not $leaf.StartsWith(
            'worktime-statistics-browser-',
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "Refusing to remove unsafe browser profile path: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) {
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            try {
                Remove-Item -LiteralPath $fullPath -Recurse -Force
                return
            } catch {
                if ($attempt -eq 19) { throw }
                Start-Sleep -Milliseconds 250
            }
        }
    }
}

function Invoke-WorkhoursLauncher {
    $repoRoot = [System.IO.Path]::GetFullPath(
        (Join-Path $PSScriptRoot '..')
    )
    Set-Location -LiteralPath $repoRoot

    $poetry = Get-RequiredCommandPath -Name 'poetry'
    $npm = Get-RequiredCommandPath -Name 'npm'
    $browser = Get-WorkhoursBrowserPath
    $serverProcess = $null
    $browserProcess = $null
    $profileDir = $null

    if (Test-WorkhoursTcpPort -Port 8000) {
        throw 'Port 8000 is already in use. Stop its current listener and try again.'
    }

    try {
        if (-not (Test-Path -LiteralPath 'backend\.venv\Scripts\python.exe')) {
            Write-Host 'Installing backend dependencies...' -ForegroundColor Cyan
            Invoke-CheckedCommand `
                -FilePath $poetry `
                -ArgumentList @('-C', 'backend', 'install') `
                -Stage 'Backend dependency installation'
        }

        if (-not (Test-Path -LiteralPath 'frontend\node_modules')) {
            Write-Host 'Installing frontend dependencies...' -ForegroundColor Cyan
            Invoke-CheckedCommand `
                -FilePath $npm `
                -ArgumentList @('--prefix', 'frontend', 'install') `
                -Stage 'Frontend dependency installation'
        }

        Write-Host 'Building frontend...' -ForegroundColor Cyan
        Invoke-CheckedCommand `
            -FilePath $npm `
            -ArgumentList @('--prefix', 'frontend', 'run', 'build') `
            -Stage 'Frontend build'

        Write-Host 'Starting Workhours...' -ForegroundColor Cyan
        $serverProcess = Start-Process `
            -FilePath $poetry `
            -ArgumentList @(
                '-C', 'backend', 'run', 'uvicorn', 'backend.main:app',
                '--host', '127.0.0.1', '--port', '8000'
            ) `
            -WorkingDirectory $repoRoot `
            -NoNewWindow `
            -PassThru

        Wait-WorkhoursHealth -ServerProcess $serverProcess

        $profileDir = Join-Path (
            [System.IO.Path]::GetTempPath()
        ) ("worktime-statistics-browser-{0}" -f [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $profileDir | Out-Null

        $browserArguments = @(
            '--app=http://127.0.0.1:8000',
            "--user-data-dir=`"$profileDir`"",
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-background-mode'
        )
        $browserProcess = Start-Process `
            -FilePath $browser `
            -ArgumentList $browserArguments `
            -PassThru

        Write-Host 'Close the Workhours window to stop the service.' -ForegroundColor Green
        Wait-Process -Id $browserProcess.Id
        Write-Host 'Workhours window closed. Stopping service...' -ForegroundColor Cyan
    } finally {
        Stop-WorkhoursProcessTree -Process $serverProcess
        Remove-WorkhoursTemporaryProfile -ProfilePath $profileDir
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        Invoke-WorkhoursLauncher
        exit 0
    } catch {
        Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}
```

- [ ] **Step 4: Run the native unit tests and verify GREEN**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/tests/start-workhours.tests.ps1
```

Expected: exit code 0 and `PowerShell launcher unit tests passed.` No project dependency or browser process is required by this unit test.

- [ ] **Step 5: Parse the production script with Windows PowerShell**

Run:

```powershell
powershell.exe -NoProfile -Command "[void][scriptblock]::Create((Get-Content -Raw 'scripts/start-workhours.ps1')); 'PowerShell syntax OK'"
```

Expected: exit code 0 and `PowerShell syntax OK`.

- [ ] **Step 6: Commit the lifecycle manager and tests**

```powershell
git add scripts/start-workhours.ps1 scripts/tests/start-workhours.tests.ps1
git commit -m "feat: manage local app lifecycle on Windows"
```

Expected: one commit containing only the PowerShell lifecycle manager and its native tests.

### Task 2: Double-click entry point, documentation, and end-to-end verification

**Files:**
- Create: `start-workhours.cmd`
- Modify: `README.md`

**Interfaces:**
- Consumes: `scripts/start-workhours.ps1` from Task 1; its zero exit means a normal browser-window close, and non-zero exit means startup or cleanup failed.
- Produces: a root double-click entry point and user-facing instructions for automatic and manual launch flows.

- [ ] **Step 1: Add a failing entry-point check**

Run before creating the wrapper:

```powershell
if (Test-Path -LiteralPath 'start-workhours.cmd') {
    throw 'start-workhours.cmd unexpectedly exists before the RED check.'
}
throw 'Expected RED: start-workhours.cmd does not exist.'
```

Expected: non-zero exit with `Expected RED: start-workhours.cmd does not exist.`

- [ ] **Step 2: Create the minimal double-click wrapper**

Create `start-workhours.cmd`:

```bat
@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\start-workhours.ps1"
set "WORKHOURS_EXIT=%ERRORLEVEL%"

if not "%WORKHOURS_EXIT%"=="0" (
    echo.
    echo Workhours failed to start. Review the error above.
    pause
)

exit /b %WORKHOURS_EXIT%
```

- [ ] **Step 3: Add the one-click section to README**

Insert this section immediately before `## 安装、构建与运行` in `README.md`:

````markdown
## Windows 一键启动

在资源管理器中双击仓库根目录的 `start-workhours.cmd`：

1. 首次运行会把 Python 依赖安装到 `backend/.venv`，并安装 `frontend/node_modules`；不会修改全局 Python 环境。
2. 每次运行都会重新构建前端并启动本机 FastAPI 服务。
3. 服务健康后会打开独立的 Edge/Chrome 应用窗口。
4. 关闭这个专用窗口后，本次启动的 Uvicorn 服务会自动停止。

如果 8000 端口已被占用、缺少 Poetry/npm/Edge/Chrome，或依赖安装与构建失败，启动窗口会保留错误信息。脚本不会关闭已有浏览器，也不会终止未知的 8000 端口进程。

下面的手动命令仍适用于开发和排错。
````

- [ ] **Step 4: Verify the wrapper structure without launching the app**

Run:

```powershell
$content = Get-Content -Raw 'start-workhours.cmd'
if ($content -notmatch 'cd /d "%~dp0"') { throw 'Wrapper does not fix its working directory.' }
if ($content -notmatch '-ExecutionPolicy Bypass') { throw 'Wrapper does not use process-local policy bypass.' }
if ($content -notmatch 'scripts\\start-workhours\.ps1') { throw 'Wrapper does not invoke the lifecycle script.' }
'CMD wrapper checks passed.'
```

Expected: exit code 0 and `CMD wrapper checks passed.`

- [ ] **Step 5: Run the real launcher and verify browser-close cleanup**

Run this from a PowerShell terminal. It launches the real app, waits for health, closes only browser processes that use the launcher's unique profile, waits for the wrapper, and asserts port cleanup:

```powershell
$beforeBrowserIds = @(
    Get-Process msedge, chrome -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Id
)
$launcher = Start-Process `
    -FilePath 'cmd.exe' `
    -ArgumentList @('/c', 'start-workhours.cmd') `
    -WorkingDirectory (Get-Location).Path `
    -PassThru

$healthy = $false
for ($attempt = 0; $attempt -lt 120; $attempt++) {
    try {
        $health = Invoke-RestMethod `
            -Uri 'http://127.0.0.1:8000/api/health' `
            -TimeoutSec 2
        if ($health.status -eq 'ok') {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
if (-not $healthy) { throw 'Launcher did not produce a healthy service.' }

$index = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -TimeoutSec 5
if ($index.StatusCode -ne 200 -or $index.Content -notmatch '工时 · Workhours') {
    throw 'Launcher did not serve the expected frontend.'
}

$dedicated = @()
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    $dedicated = @(
        Get-CimInstance Win32_Process |
            Where-Object {
                $_.Name -in @('msedge.exe', 'chrome.exe') -and
                $_.CommandLine -like '*worktime-statistics-browser-*'
            }
    )
    if ($dedicated.Count -gt 0) { break }
    Start-Sleep -Milliseconds 250
}
if ($dedicated.Count -eq 0) { throw 'Dedicated browser profile process was not found.' }
$reusedBrowserIds = @(
    $dedicated |
        Where-Object { $_.ProcessId -in $beforeBrowserIds } |
        Select-Object -ExpandProperty ProcessId
)
if ($reusedBrowserIds.Count -gt 0) {
    throw "Launcher reused existing browser processes: $($reusedBrowserIds -join ', ')"
}
$dedicated | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

if (-not $launcher.WaitForExit(15000)) {
    throw 'Launcher did not exit after the dedicated browser closed.'
}
if ($launcher.ExitCode -ne 0) {
    throw "Launcher returned exit code $($launcher.ExitCode)."
}
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8000 is still listening after browser close.'
}

'End-to-end launcher verification passed.'
```

Expected: the dedicated app window appears, the health and index checks pass, only processes using the unique launcher profile are stopped, the wrapper exits with code 0, and port 8000 is free.

- [ ] **Step 6: Run full regression verification**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/tests/start-workhours.tests.ps1
poetry -C backend run pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

Expected:

- Native launcher tests print `PowerShell launcher unit tests passed.`
- Backend reports `78 passed` with only the existing Starlette TestClient deprecation warning.
- Frontend reports 3 files and 10 tests passed.
- TypeScript and Vite build complete successfully.
- `git diff --check` prints nothing.
- Before the final commit, `git status --short` lists only `README.md` and `start-workhours.cmd` for Task 2.

- [ ] **Step 7: Commit the entry point and documentation**

```powershell
git add start-workhours.cmd README.md
git commit -m "feat: add one-click Windows startup"
```

Expected: a second focused commit containing the CMD entry point and README update.

- [ ] **Step 8: Verify the final repository state**

Run:

```powershell
git status --short
git log -3 --oneline
```

Expected: clean tracked working tree. The newest two implementation commits are `feat: add one-click Windows startup` and `feat: manage local app lifecycle on Windows`.
