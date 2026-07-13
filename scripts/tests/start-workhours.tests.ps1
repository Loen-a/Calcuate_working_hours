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
