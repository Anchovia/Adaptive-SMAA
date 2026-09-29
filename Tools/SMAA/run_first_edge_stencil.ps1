param(
    [ValidateSet('Capture','Smoke','Benchmark')][string] $Phase='Capture',
    [ValidateSet('bistro','minecraft')][string] $Scene='bistro',
    [string] $CaptureRoot='D:/SMAAResearchCaptures/first-edge-stencil-20260929',
    [string] $Receipt='tmp/first-edge-stencil-item5-runs.json',
    [switch] $Isolation
)
$ErrorActionPreference='Stop'
if($Isolation){throw 'The spatial-stencil isolation matrix belongs to item6; item5 has no spatial weight pass'}
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$hash=(Get-FileHash -LiteralPath $exe).Hash
$audit=Get-Content (Join-Path $root 'Docs/First-Edge-Temporal-Only-Stencil/source-audit.json') -Raw | ConvertFrom-Json
if($hash -ne $audit.executable_sha256){throw 'Executable differs from audited build'}
# HLSL is loaded from disk: an unchanged exe alone cannot identify the tested shader.
$byteEncoding=[Text.Encoding]::GetEncoding(28591)
$sha256=[Security.Cryptography.SHA256]::Create()
try {
    $sources=@{}
    foreach($p in $audit.source_sha256_lf.PSObject.Properties){$sources[$p.Name]=$p.Value}
    foreach($p in $audit.native_shader_unchanged.PSObject.Properties){
        if($p.Name.EndsWith('.hlsl')){$sources["Projects/CMAA2/SMAA/$($p.Name)"]=$p.Value}
    }
    foreach($source in $sources.Keys){
        $bytes=[IO.File]::ReadAllBytes((Join-Path $root $source))
        $normalized=$byteEncoding.GetBytes($byteEncoding.GetString($bytes).Replace("`r`n","`n"))
        $actual=[BitConverter]::ToString($sha256.ComputeHash($normalized)).Replace('-','').ToLowerInvariant()
        if($actual -ne $sources[$source]){throw "Source differs from audited capture: $source"}
    }
} finally {$sha256.Dispose()}
if($CaptureRoot -match '\s' -or ![System.IO.Path]::IsPathRooted($CaptureRoot)){throw 'Capture root must be absolute without spaces'}
$records=@()
if(Test-Path -LiteralPath $Receipt){$records=@(Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json)}
if(@($records | Where-Object {$_.scene -eq $Scene -and $_.phase -eq $Phase}).Count){throw 'Already completed; use a new receipt for independent run'}
$started=[DateTime]::UtcNow.ToString('o')
$kind=if($Isolation){'Isolation'}else{''}
if($Phase -eq 'Benchmark'){
    $suffix=if($Isolation){'isolation-capture'}else{'capture'}
    $gatePath=Join-Path $root "Docs/First-Edge-Temporal-Only-Stencil/$Scene-$suffix.json"
    if(!(Test-Path -LiteralPath $gatePath)){throw 'Execution/output capture gate is required before benchmarking'}
    $gate=Get-Content -LiteralPath $gatePath -Raw | ConvertFrom-Json
    if($gate.validation -ne 'PASS' -or $gate.executable_sha256 -ne $hash){throw 'Capture gate must pass for this exact executable'}
    if(!$gate.mismatches -or @($gate.mismatches.PSObject.Properties | Where-Object {$_.Value -ne 0}).Count){throw 'Coverage or output mismatch remains'}
    $bridgePath=Join-Path $root "Docs/First-Edge-Temporal-Only-Stencil/$Scene-input-bridge.json"
    if(!(Test-Path -LiteralPath $bridgePath)){throw 'RGBA/velocity and item5/item6 edge bridge is required'}
    $bridge=Get-Content -LiteralPath $bridgePath -Raw | ConvertFrom-Json
    if($bridge.validation -ne 'PASS' -or $bridge.executable_sha256 -ne $hash -or $bridge.capture_gate_sha256 -ne (Get-FileHash -LiteralPath $gatePath).Hash){throw 'Input bridge does not match this capture gate'}
    if(!$bridge.mismatches -or @($bridge.mismatches.PSObject.Properties | Where-Object {$_.Value -ne 0}).Count){throw 'Input bridge mismatch remains'}
}
$arguments=@("-smaaFirstEdgeStencil$kind$Phase",$Scene,$CaptureRoot)
$output=& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 1200
$pass=$output | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass){throw 'No completed result'}
$report=($pass -split 'report=',2)[1].Trim()
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed'}
$records += [pscustomobject]@{scene=$Scene;phase=$Phase;item=5;window='hidden';base='c51ca28';branch='experiment/first-edge-temporal-only-stencil';arguments=$arguments;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');executable_sha256=$hash;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash;scope='process-and-completeness-only; analyze_first_edge_stencil.py acceptance required'}
ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $Receipt -Encoding utf8
Write-Output $pass
