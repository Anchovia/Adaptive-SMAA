param(
    [Parameter(Mandatory = $true)]
    [string] $CachePath,

    [ValidateSet(
        'yaw-slow-360', 'yaw-fast-360', 'yaw-extreme-360',
        'strafe-fast', 'yaw-strafe-fast', 'yaw-smooth-360',
        'flythrough-smooth', 'flythrough-smooth-yaw-360',
        'flythrough-wide', 'flythrough-wide-yaw-360')]
    [string] $CameraProfile = 'yaw-fast-360',

    [ValidateRange(0, 479)]
    [int] $FirstProfileFrame = 60,

    [ValidateRange(1, 480)]
    [int] $CaptureFrames = 60,

    [ValidateRange(0, 600)]
    [int] $WarmupFrames = 60,

    [ValidateRange(0.0, 1.0)]
    [double] $MinimumThreshold = 0.0,

    [ValidateRange(0.0, 1.0)]
    [double] $MaximumThreshold = 1.0,

    [ValidateRange(0.01, 1.0)]
    [double] $ThresholdStep = 0.05,

    [ValidateRange(30, 86400)]
    [int] $TimeoutSeconds = 1200,

    [switch] $Hidden
)

$ErrorActionPreference = 'Stop'

if ($MinimumThreshold -gt $MaximumThreshold) {
    throw 'MinimumThreshold must be <= MaximumThreshold'
}

$resolvedCache = (Resolve-Path -LiteralPath $CachePath).Path
if ([IO.Path]::GetExtension($resolvedCache) -ne '.smaasm') {
    throw "Expected a .smaasm cache: $resolvedCache"
}

$cleanRunner = Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$autoBenchRoot = Join-Path $repositoryRoot 'Projects\CMAA2\AutoBench'
if (-not (Test-Path -LiteralPath $cleanRunner -PathType Leaf)) {
    throw "Clean CMAA2 runner not found: $cleanRunner"
}
if (-not (Test-Path -LiteralPath $autoBenchRoot -PathType Container)) {
    throw "AutoBench root not found: $autoBenchRoot"
}

$thresholds = [Collections.Generic.List[double]]::new()
$value = $MinimumThreshold
while ($value -le $MaximumThreshold + 1e-9) {
    $thresholds.Add([Math]::Round($value, 6))
    $value += $ThresholdStep
}
if ([Math]::Abs($thresholds[$thresholds.Count - 1] - $MaximumThreshold) -gt 1e-6) {
    $thresholds.Add($MaximumThreshold)
}

$captureSpec = 'sanmiguel {0} O-ET2X-R {1} {2} {3}' -f @(
    $CameraProfile,
    $FirstProfileFrame,
    $CaptureFrames,
    $WarmupFrames
)
$runnerParameters = @{ TimeoutSeconds = $TimeoutSeconds }
if ($Hidden) {
    $runnerParameters.Hidden = $true
}

function Get-CaptureRoots {
    return @(Get-ChildItem -LiteralPath $autoBenchRoot -Directory |
        Where-Object { $_.Name -match '^\d{8}_\d{6}$' })
}

function Invoke-ThresholdCapture {
    param(
        [double] $Threshold,
        [bool] $CandidateMask
    )

    $before = @{}
    foreach ($directory in Get-CaptureRoots) {
        $before[$directory.FullName] = $true
    }
    $thresholdText = $Threshold.ToString(
        '0.00', [Globalization.CultureInfo]::InvariantCulture)
    $arguments = @(
        '-smaaSanMiguelCache', $resolvedCache,
        '-smaaCandidateExpansionOverride', '3',
        '-smaaArmDualReconstructionThresholdOverride', $thresholdText
    )
    if ($CandidateMask) {
        $arguments += @('-smaaTemporalDebugView', '2')
    }
    $arguments += @('-smaaCameraMotionSingleModeCapture', $captureSpec)

    $kind = if ($CandidateMask) { 'candidate-mask' } else { 'final-color' }
    Write-Host "Starting ARM threshold $thresholdText $kind capture"
    $runnerOutput = & $cleanRunner -CMAA2Arguments $arguments @runnerParameters
    $runnerOutput | ForEach-Object { Write-Host $_ }

    $created = @(Get-CaptureRoots | Where-Object { -not $before.ContainsKey($_.FullName) })
    if ($created.Count -ne 1) {
        throw "Expected exactly one new AutoBench root for threshold $thresholdText $kind; found $($created.Count)"
    }
    return $created[0].FullName
}

$manifestDirectory = Join-Path $autoBenchRoot (
    'ARM-Threshold-Sweep-{0}' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $manifestDirectory | Out-Null
$records = [Collections.Generic.List[object]]::new()

foreach ($threshold in $thresholds) {
    $finalRoot = Invoke-ThresholdCapture -Threshold $threshold -CandidateMask $false
    $maskRoot = Invoke-ThresholdCapture -Threshold $threshold -CandidateMask $true
    $records.Add([pscustomobject]@{
        threshold = $threshold
        final_capture_root = $finalRoot
        candidate_mask_root = $maskRoot
    })
    $records | Export-Csv -LiteralPath (Join-Path $manifestDirectory 'arm_threshold_sweep.csv') `
        -NoTypeInformation -Encoding utf8
}

$manifest = [ordered]@{
    classification = 'ARM candidate-mask reconstruction threshold research sweep'
    scene = 'sanmiguel'
    camera_profile = $CameraProfile
    first_profile_frame = $FirstProfileFrame
    capture_frames = $CaptureFrames
    warmup_frames = $WarmupFrames
    threshold_minimum = $MinimumThreshold
    threshold_maximum = $MaximumThreshold
    threshold_step = $ThresholdStep
    expansion = 'ArmDualFilter with raw candidate union'
    temporal_mode = 'O-ET2X-R document profile; camera/depth reprojection'
    thresholds = @($records)
}
$manifest | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $manifestDirectory 'arm_threshold_sweep.json') `
        -Encoding utf8

Write-Output "PASS: ARM threshold sweep completed: $manifestDirectory"
