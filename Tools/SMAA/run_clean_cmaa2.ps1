param(
    [Parameter(Mandatory = $true)]
    [AllowEmptyCollection()]
    [string[]] $CMAA2Arguments,

    [ValidateRange(30, 86400)]
    [int] $TimeoutSeconds = 600,

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

$autoBenchRoot = Join-Path $repositoryRoot 'Projects\CMAA2\AutoBench'
$expectsAutoBenchReport = @($CMAA2Arguments | Where-Object {
    $_ -match '^-[^\s]*(Test|Capture|Smoke|Benchmark)$'
}).Count -ne 0
$reportsBefore = @{}
if ($expectsAutoBenchReport -and (Test-Path -LiteralPath $autoBenchRoot -PathType Container)) {
    foreach ($report in Get-ChildItem -LiteralPath $autoBenchRoot -Directory |
        ForEach-Object {
            Get-ChildItem -LiteralPath $_.FullName -File -Filter '*_results.csv' `
                -ErrorAction SilentlyContinue
        }) {
        $reportsBefore[$report.FullName] = '{0}:{1}' -f @(
            $report.Length, $report.LastWriteTimeUtc.Ticks)
    }
}

$startParameters = @{
    FilePath = $executable
    ArgumentList = $CMAA2Arguments
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
    throw "CMAA2 exceeded the $TimeoutSeconds-second timeout and was terminated"
}
if ($process.ExitCode -ne 0) {
    throw "CMAA2 exited with code $($process.ExitCode)"
}

$completedReports = @()
if ($expectsAutoBenchReport -and (Test-Path -LiteralPath $autoBenchRoot -PathType Container)) {
    $completedReports = @(Get-ChildItem -LiteralPath $autoBenchRoot -Directory |
        ForEach-Object {
            Get-ChildItem -LiteralPath $_.FullName -File -Filter '*_results.csv' `
                -ErrorAction SilentlyContinue
        } | Where-Object {
            $fingerprint = '{0}:{1}' -f @($_.Length, $_.LastWriteTimeUtc.Ticks)
            -not $reportsBefore.ContainsKey($_.FullName) -or
                $reportsBefore[$_.FullName] -ne $fingerprint
        })
    if ($completedReports.Count -eq 0) {
        throw 'CMAA2 exited without a new finalized AutoBench results CSV; treating the run as failed'
    }
}

$reportSuffix = if ($completedReports.Count -gt 0) {
    "; report=$($completedReports[-1].FullName)"
} else {
    ''
}
Write-Output "PASS: clean CMAA2 process exited normally (PID $($process.Id))$reportSuffix"
