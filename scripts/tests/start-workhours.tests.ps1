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
$missing = $null
$fakeTaskkillDir = $null
$cleanupProcess = $null
$originalPath = $env:PATH

try {
    $missing = Join-Path (
        [System.IO.Path]::GetTempPath()
    ) ("workhours-missing-browser-{0}.exe" -f [guid]::NewGuid().ToString('N'))
    Remove-Item -LiteralPath $missing -Force -ErrorAction SilentlyContinue
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

    $fakeTaskkillDir = Join-Path (
        [System.IO.Path]::GetTempPath()
    ) ("workhours-fake-taskkill-{0}" -f [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $fakeTaskkillDir | Out-Null
    Copy-Item `
        -LiteralPath $env:ComSpec `
        -Destination (Join-Path $fakeTaskkillDir 'taskkill.exe')
    $cleanupProcess = Start-Process `
        -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 60') `
        -PassThru
    $env:PATH = "$fakeTaskkillDir;$originalPath"

    $cleanupError = $null
    try {
        Stop-WorkhoursProcessTree -Process $cleanupProcess
    } catch {
        $cleanupError = $_.Exception
    }
    Assert-True ([bool]$cleanupError) 'Failed taskkill did not raise an error.'
    Assert-True (
        $cleanupError.Message.Contains("PID $($cleanupProcess.Id)")
    ) 'Cleanup error did not include the process ID.'
    Assert-True (
        $cleanupError.Message.Contains('exit code')
    ) 'Cleanup error did not include the taskkill exit code.'
    $cleanupProcess.Refresh()
    Assert-True (-not $cleanupProcess.HasExited) 'Failed taskkill unexpectedly stopped the process.'

    $script:healthProbeCount = 0
    $script:healthSleepMilliseconds = 0
    function Invoke-RestMethod {
        param([string]$Uri, [int]$TimeoutSec)

        $script:healthProbeCount++
        if ($script:healthProbeCount -eq 1) {
            return [pscustomobject]@{ status = 'starting' }
        }
        return [pscustomobject]@{ status = 'ok' }
    }
    function Start-Sleep {
        param([int]$Milliseconds)

        $script:healthSleepMilliseconds += $Milliseconds
    }
    try {
        Wait-WorkhoursHealth `
            -ServerProcess ([System.Diagnostics.Process]::GetCurrentProcess()) `
            -TimeoutSeconds 1
    } finally {
        Remove-Item -LiteralPath Function:\Invoke-RestMethod
        Remove-Item -LiteralPath Function:\Start-Sleep
    }
    Assert-Equal 2 $script:healthProbeCount 'Health endpoint was not retried.'
    Assert-Equal `
        250 `
        $script:healthSleepMilliseconds `
        'Non-healthy response did not wait before retrying.'

    Write-Host 'PowerShell launcher unit tests passed.' -ForegroundColor Green
} finally {
    $env:PATH = $originalPath
    if ($cleanupProcess -and -not $cleanupProcess.HasExited) {
        Stop-Process -Id $cleanupProcess.Id -Force -ErrorAction SilentlyContinue
        [void]$cleanupProcess.WaitForExit(5000)
    }
    if ($fakeTaskkillDir -and (Test-Path -LiteralPath $fakeTaskkillDir)) {
        Remove-Item -LiteralPath $fakeTaskkillDir -Recurse -Force
    }
    if ($listener) { $listener.Stop() }
    if ($profileDir -and (Test-Path -LiteralPath $profileDir)) {
        Remove-Item -LiteralPath $profileDir -Recurse -Force
    }
    if ($missing) {
        Remove-Item -LiteralPath $missing -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $tempFile.FullName -Force -ErrorAction SilentlyContinue
}
