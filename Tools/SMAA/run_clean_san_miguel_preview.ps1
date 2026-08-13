param(
    [Parameter(Mandatory = $true)]
    [string] $CachePath,

    [ValidateRange(0, 600)]
    [int] $WarmupFrames = 10,

    [ValidateRange(30, 600)]
    [int] $TimeoutSeconds = 240,

    [switch] $Hidden
)

$ErrorActionPreference = 'Stop'
$existing = @(Get-Process -Name 'CMAA2' -ErrorAction SilentlyContinue)
if ($existing.Count -ne 0) {
    $ids = ($existing | ForEach-Object { $_.Id }) -join ', '
    throw "Clean-process precondition failed: CMAA2 PID(s) already running: $ids"
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$executable = Join-Path $repositoryRoot 'Projects\CMAA2\CMAA2.exe'
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Release executable not found: $executable"
}
$resolvedCache = (Resolve-Path -LiteralPath $CachePath).Path
if ([IO.Path]::GetExtension($resolvedCache) -ne '.smaasm') {
    throw "Expected a .smaasm cache: $resolvedCache"
}

$arguments = @(
    '-smaaSanMiguelCache', "`"$resolvedCache`"",
    '-smaaSanMiguelPreviewCapture', "`"$WarmupFrames`""
)
$startParameters = @{
    FilePath = $executable
    ArgumentList = $arguments
    WorkingDirectory = (Split-Path -Parent $executable)
    PassThru = $true
}
if ($Hidden) {
    $startParameters.WindowStyle = 'Hidden'
}

$process = Start-Process @startParameters
$timedOut = -not $process.WaitForExit($TimeoutSeconds * 1000)
if ($timedOut) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    $process.WaitForExit()
}

Start-Sleep -Milliseconds 500
$remaining = @(Get-Process -Name 'CMAA2' -ErrorAction SilentlyContinue)
if ($remaining.Count -ne 0) {
    throw 'Clean-process postcondition failed: CMAA2.exe is still running'
}
if ($timedOut) {
    throw "San Miguel preview exceeded the $TimeoutSeconds-second process timeout and was terminated"
}
if ($process.ExitCode -ne 0) {
    throw "San Miguel preview exited with code $($process.ExitCode)"
}

Write-Output "PASS: clean CMAA2 process exited normally (PID $($process.Id))"
