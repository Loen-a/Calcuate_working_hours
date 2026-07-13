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
$ownershipListener = $null
$unrelatedProcess = $null
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

    $argumentProfile = Join-Path (
        [System.IO.Path]::GetTempPath()
    ) ("worktime-statistics-browser-args-{0}" -f [guid]::NewGuid().ToString('N'))
    $browserArguments = Get-WorkhoursBrowserArguments -ProfilePath $argumentProfile
    Assert-True ($browserArguments -contains '--new-window') 'Normal-window flag is missing.'
    Assert-True (
        $browserArguments -contains 'http://127.0.0.1:8000'
    ) 'Workhours URL is missing from browser arguments.'
    Assert-True (
        $browserArguments -contains '--disable-extensions'
    ) 'Disposable browser extensions are not disabled.'
    Assert-True (
        $browserArguments -contains '--disable-sync'
    ) 'Disposable browser sync is not disabled.'
    Assert-True (
        -not @($browserArguments | Where-Object { $_ -like '--app=*' }).Count
    ) 'Browser arguments still contain app mode.'
    Assert-True (
        @($browserArguments | Where-Object { $_ -like '--user-data-dir=*' }).Count -eq 1
    ) 'Exactly one disposable profile argument is required.'

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

    $ownershipListener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    $ownershipListener.Start()
    $ownershipPort = ([System.Net.IPEndPoint]$ownershipListener.LocalEndpoint).Port
    Assert-WorkhoursListenerOwnership `
        -Port $ownershipPort `
        -RootProcess ([System.Diagnostics.Process]::GetCurrentProcess())

    $unrelatedProcess = Start-Process `
        -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 60') `
        -PassThru
    $ownershipError = $null
    try {
        Assert-WorkhoursListenerOwnership `
            -Port $ownershipPort `
            -RootProcess $unrelatedProcess
    } catch {
        $ownershipError = $_.Exception
    }
    Assert-True ([bool]$ownershipError) 'Unrelated listener was accepted as the recorded service.'
    Assert-True (
        $ownershipError.Message.Contains('not owned')
    ) 'Unrelated listener error did not explain the ownership failure.'
    $ownershipListener.Stop()
    $ownershipListener = $null

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

    $profileDir = Join-Path (
        [System.IO.Path]::GetTempPath()
    ) ("worktime-statistics-browser-test-{0}" -f [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $profileDir | Out-Null
    Set-Content -LiteralPath (Join-Path $profileDir 'marker.txt') -Value 'test'
    $combinedCleanupError = $null
    try {
        Invoke-WorkhoursCleanup `
            -ServerProcess $cleanupProcess `
            -ProfilePath $profileDir
    } catch {
        $combinedCleanupError = $_.Exception
    }
    Assert-True ([bool]$combinedCleanupError) 'Launcher cleanup did not propagate the process error.'
    Assert-True (
        $combinedCleanupError.Message.Contains("PID $($cleanupProcess.Id)")
    ) 'Launcher cleanup error did not include the process ID.'
    Assert-True (
        -not (Test-Path -LiteralPath $profileDir)
    ) 'Temporary profile was not removed after process cleanup failed.'
    $profileDir = $null

    function Get-Command {
        param([string]$Name, $ErrorAction)
        return $null
    }
    try {
        $poetryError = $null
        try { Get-RequiredCommandPath -Name 'poetry' } catch { $poetryError = $_.Exception }
        Assert-True ([bool]$poetryError) 'Missing Poetry did not raise an error.'
        Assert-True (
            $poetryError.Message.Contains('Install Poetry') -and
            $poetryError.Message.Contains('PATH')
        ) 'Missing Poetry guidance did not mention installation and PATH.'

        $npmError = $null
        try { Get-RequiredCommandPath -Name 'npm' } catch { $npmError = $_.Exception }
        Assert-True ([bool]$npmError) 'Missing npm did not raise an error.'
        Assert-True (
            $npmError.Message.Contains('Install Node.js') -and
            $npmError.Message.Contains('npm') -and
            $npmError.Message.Contains('PATH')
        ) 'Missing npm guidance did not mention Node.js/npm installation and PATH.'
    } finally {
        Remove-Item -LiteralPath Function:\Get-Command
    }

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
    if ($unrelatedProcess -and -not $unrelatedProcess.HasExited) {
        Stop-Process -Id $unrelatedProcess.Id -Force -ErrorAction SilentlyContinue
        [void]$unrelatedProcess.WaitForExit(5000)
    }
    if ($ownershipListener) { $ownershipListener.Stop() }
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
