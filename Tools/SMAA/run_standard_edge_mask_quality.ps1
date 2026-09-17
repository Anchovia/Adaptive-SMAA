param(
    [ValidateSet('bistro', 'minecraft')][string] $Scene = 'bistro',
    [string] $Receipt = 'tmp/standard-edge-mask-quality-runs.json'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$records = @()
if (Test-Path -LiteralPath $Receipt) {
    $records = @(Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json)
}
if (@($records | Where-Object { $_.scene -eq $Scene }).Count -gt 0) {
    throw "Receipt already contains $Scene. Use a new receipt for a new capture set."
}
$receiptDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($Receipt))
New-Item -ItemType Directory -Path $receiptDirectory -Force | Out-Null
foreach ($mode in @('O-T2X-R', 'ABL-Standard-EdgeMask-R')) {
    $arguments = @('-smaaCandidateStatisticsReadback','0',
        '-smaaObjectMotionReprojectionOverride','0',
        '-smaaDisocclusionRejectionOverride','0','-smaaTemporalDebugView','0',
        '-smaaCameraMotionSingleModeCapture',
        ('"{0} flythrough-wide-yaw-360 {1} 0 480 60"' -f $Scene, $mode))
    $output = & (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') `
        -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 600
    $line = $output | Where-Object { $_ -match 'PASS:.*report=' } | Select-Object -Last 1
    if (!$line) { throw "Capture did not complete: $Scene/$mode" }
    $records += [pscustomobject]@{
        scene=$Scene; mode=$mode; arguments=$arguments
        report=($line -split 'report=',2)[1].Trim()
        executable_sha256=(Get-FileHash (Join-Path $root 'Projects/CMAA2/CMAA2.exe')).Hash
        window='hidden'; purpose='complete-timeline native coverage-only quality comparison'
    }
    ConvertTo-Json -InputObject @($records) -Depth 6 | Set-Content -LiteralPath $Receipt
    Write-Output "$Scene/$mode $line"
}
