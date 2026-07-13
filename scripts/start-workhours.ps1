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
