param(
    [ValidateSet('Quality', 'Performance', 'Lifecycle', 'FinalBuildBridge')]
    [string] $Phase = 'Quality',
    [ValidateSet('bistro', 'minecraft')]
    [string] $Scene = 'bistro',
    [int] $Frames = 12,
    [string] $Receipt = 'tmp/standard-edge-mask-runs.json'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runner = Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1'
$receipts = @()
if (Test-Path -LiteralPath $Receipt) {
    $receipts = @(Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json)
}
function Run-Gate([string] $Label, [string[]] $Arguments, [bool] $Hidden) {
    $output = & $runner -CMAA2Arguments $Arguments -TimeoutSeconds 600 -Hidden:$Hidden
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Gate failed: $Label" }
    $line = ($output | Where-Object { $_ -match 'PASS:.*report=' } | Select-Object -Last 1)
    if (!$line) { throw "Missing completed report for $Label" }
    $report = ($line -split 'report=', 2)[1].Trim()
    $record = [pscustomobject]@{
        phase=$Phase; scene=$Scene; label=$Label; report=$report
        arguments=$Arguments; window=$(if($Hidden){'hidden'}else{'visible'})
        executable_sha256=(Get-FileHash (Join-Path $root 'Projects/CMAA2/CMAA2.exe')).Hash
    }
    $script:receipts += $record
    ConvertTo-Json -InputObject @($script:receipts) -Depth 6 | Set-Content -LiteralPath $Receipt
    Write-Output "$Label $line"
}
# Each command owns a fresh process; the clean runner enforces pre/post-zero and timeout.
$common = @('-smaaCandidateStatisticsReadback', '0',
    '-smaaObjectMotionReprojectionOverride', '0', '-smaaDisocclusionRejectionOverride', '0')
if ($Phase -eq 'Quality') {
    foreach ($entry in @(
        @('standard', 'O-T2X-R', 0),
        @('masked', 'ABL-Standard-EdgeMask-R', 0),
        @('spatial', 'O-T2X-R', 3),
        @('mask', 'ABL-Standard-EdgeMask-R', 1),
        @('masked-repeat', 'ABL-Standard-EdgeMask-R', 0))) {
        $value = '"{0} flythrough-wide-yaw-360 {1} 150 {2} 60"' -f $Scene, $entry[1], $Frames
        Run-Gate $entry[0] ($common + @('-smaaTemporalDebugView', "$($entry[2])",
            '-smaaCameraMotionSingleModeCapture', $value)) $true
    }
} elseif ($Phase -eq 'FinalBuildBridge') {
    Run-Gate 'masked-final-build' ($common + @('-smaaTemporalDebugView', '0',
        '-smaaCameraMotionSingleModeCapture',
        ('"{0} flythrough-wide-yaw-360 ABL-Standard-EdgeMask-R 150 {1} 60"' -f $Scene, $Frames))) $true
} elseif ($Phase -eq 'Performance') {
    # Visible-window repeated timing; capture/readbacks/debug outputs are disabled.
    Run-Gate 'paired' ($common + @('-smaaTemporalDebugView', '0',
        '-smaaStandardEdgeMaskPerformanceBenchmark', ('"{0} 1 300 4800 3"' -f $Scene))) $false
} else {
    Run-Gate 'lifecycle' ($common + @('-smaaTemporalDebugView', '0',
        '-smaaTemporalLifecycleTest')) $true
}
