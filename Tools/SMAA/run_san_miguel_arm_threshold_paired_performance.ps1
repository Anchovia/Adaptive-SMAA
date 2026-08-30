param(
    [Parameter(Mandatory = $true)]
    [string] $CachePath,

    [ValidateRange(8, 600)]
    [int] $WarmupFrames = 300,

    [ValidateRange(16, 60)]
    [int] $MeasureFrames = 60,

    [ValidateRange(1, 9)]
    [int] $Repeats = 3,

    [ValidateRange(30, 86400)]
    [int] $TimeoutSeconds = 2400,

    [switch] $Hidden
)

$ErrorActionPreference = 'Stop'
$resolvedCache = (Resolve-Path -LiteralPath $CachePath).Path
if ([IO.Path]::GetExtension($resolvedCache) -ne '.smaasm') {
    throw "Expected a .smaasm cache: $resolvedCache"
}
$cleanRunner = Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$autoBenchRoot = Join-Path $repositoryRoot 'Projects\CMAA2\AutoBench'

$before = @{}
foreach ($directory in Get-ChildItem -LiteralPath $autoBenchRoot -Directory |
    Where-Object { $_.Name -match '^\d{8}_\d{6}$' }) {
    $before[$directory.FullName] = $true
}
$command = if ($Repeats -gt 1) {
    '-smaaArmThresholdPerformanceBenchmark'
} else {
    '-smaaArmThresholdPerformanceSmoke'
}
$performanceSpec = 'sanmiguel 1.0 {0} {1} {2}' -f @(
    $WarmupFrames, $MeasureFrames, $Repeats)
$arguments = @(
    '-smaaSanMiguelCache', $resolvedCache,
    '-smaaCandidateStatisticsReadback', '0',
    $command, $performanceSpec
)
$runnerParameters = @{ TimeoutSeconds = $TimeoutSeconds }
if ($Hidden) {
    $runnerParameters.Hidden = $true
}

$runnerOutput = & $cleanRunner -CMAA2Arguments $arguments @runnerParameters
$runnerOutput | ForEach-Object { Write-Host $_ }
$created = @(Get-ChildItem -LiteralPath $autoBenchRoot -Directory |
    Where-Object { $_.Name -match '^\d{8}_\d{6}$' -and -not $before.ContainsKey($_.FullName) })
if ($created.Count -ne 1) {
    throw "Expected one new AutoBench root; found $($created.Count)"
}
$resultCsv = @(Get-ChildItem -LiteralPath $created[0].FullName -Filter '*_results.csv' -File)
if ($resultCsv.Count -ne 1) {
    throw "Expected one result CSV in $($created[0].FullName)"
}

$manifestDirectory = Join-Path $autoBenchRoot (
    'ARM-Threshold-Paired-Performance-{0}' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $manifestDirectory | Out-Null
$manifest = [ordered]@{
    classification = if ($Repeats -gt 1) { 'paired repeated engineering benchmark' } else { 'paired engineering smoke' }
    scene = 'sanmiguel'
    camera_profile = 'yaw-fast-360'
    first_profile_frame = 60
    warmup_frames = $WarmupFrames
    measure_frames = $MeasureFrames
    repeats = $Repeats
    candidate_statistics_readback = $false
    modes = @('3x3', 'ARM-0.10', 'ARM-0.15', 'ARM-0.20', 'ARM-0.25')
    capture_root = $created[0].FullName
    result_csv = $resultCsv[0].FullName
}
$manifest | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $manifestDirectory 'arm_threshold_paired_performance.json') `
        -Encoding utf8

Write-Output "PASS: paired ARM threshold performance completed: $manifestDirectory"
