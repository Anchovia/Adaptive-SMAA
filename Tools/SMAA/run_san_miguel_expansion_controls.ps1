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
    [double] $ArmThreshold = 0.25,

    [ValidateRange(30, 86400)]
    [int] $TimeoutSeconds = 7200,

    [switch] $SkipReference,

    [switch] $CandidateMask,

    [switch] $Hidden
)

$ErrorActionPreference = 'Stop'

$resolvedCache = (Resolve-Path -LiteralPath $CachePath).Path
if ([IO.Path]::GetExtension($resolvedCache) -ne '.smaasm') {
    throw "Expected a .smaasm cache: $resolvedCache"
}

$cleanRunner = Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1'
if (-not (Test-Path -LiteralPath $cleanRunner -PathType Leaf)) {
    throw "Clean CMAA2 runner not found: $cleanRunner"
}

$captureSpec = 'sanmiguel {0} {1} {2} {3}' -f @(
    $CameraProfile,
    $FirstProfileFrame,
    $CaptureFrames,
    $WarmupFrames
)
$thresholdText = $ArmThreshold.ToString(
    '0.00', [Globalization.CultureInfo]::InvariantCulture)

$commonArguments = @(
    '-smaaSanMiguelCache', $resolvedCache
)
$runnerParameters = @{
    TimeoutSeconds = $TimeoutSeconds
}
if ($Hidden) {
    $runnerParameters.Hidden = $true
}

if (-not $SkipReference) {
    Write-Output "Starting paired San Miguel supersample reference capture: $captureSpec"
    $referenceArguments = $commonArguments + @(
        '-smaaCameraMotionReferenceCapture', $captureSpec
    )
    & $cleanRunner -CMAA2Arguments $referenceArguments @runnerParameters
}

Write-Output (
    "Starting San Miguel expansion/control capture: {0}; ARM threshold={1}" -f
    $captureSpec, $thresholdText
)
$controlArguments = $commonArguments + @(
    '-smaaArmDualReconstructionThresholdOverride', $thresholdText,
    '-smaaCandidateExpansionControlCapture', $captureSpec
)
if ($CandidateMask) {
    $controlArguments = $commonArguments + @(
        '-smaaArmDualReconstructionThresholdOverride', $thresholdText,
        '-smaaTemporalDebugView', '2',
        '-smaaCandidateExpansionControlCapture', $captureSpec
    )
}
& $cleanRunner -CMAA2Arguments $controlArguments @runnerParameters

Write-Output 'PASS: paired San Miguel candidate-expansion control workflow completed.'
