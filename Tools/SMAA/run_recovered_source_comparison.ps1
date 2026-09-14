param(
    [Parameter(Mandatory=$true)][ValidateSet('Boundary','Quality','Masks','Benchmark')][string]$Mode,
    [ValidateSet('bistro','minecraft')][string[]]$Scenes=@('bistro','minecraft'),
    [ValidateRange(1,480)][int]$QualityFrames=480,
    [string]$Manifest='tmp/source-comparison-runs.json'
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$bench=Join-Path $repo 'Projects/CMAA2/AutoBench'
$manifestPath=[IO.Path]::GetFullPath((Join-Path $repo $Manifest))
New-Item -ItemType Directory -Force -Path (Split-Path $manifestPath) | Out-Null
$runs=@()
if(Test-Path -LiteralPath $manifestPath) { $runs=@(Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json) }
$exeHash=(Get-FileHash -LiteralPath (Join-Path $repo 'Projects/CMAA2/CMAA2.exe')).Hash
function Invoke-ComparisonRun([string]$label,[string[]]$demoArguments,[bool]$hidden) {
    $before=@(Get-ChildItem -LiteralPath $bench -Directory | ForEach-Object Name)
    & (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $demoArguments -TimeoutSeconds 1800 -Hidden:$hidden
    $new=@(Get-ChildItem -LiteralPath $bench -Directory | Where-Object { $_.Name -notin $before })
    if($new.Count -ne 1) { throw "Expected exactly one report directory for $label" }
    $entry=[ordered]@{label=$label;arguments=$demoArguments;report=$new[0].FullName;exe_sha256=$exeHash;window=$(if($hidden){'hidden'}else{'visible'});status='PASS'}
    Copy-Item -LiteralPath (Join-Path $repo 'Projects/CMAA2/log.txt') -Destination (Join-Path $new[0].FullName 'recovered-source-execution.log')
    $script:runs+= $entry
    ConvertTo-Json -Depth 8 -InputObject @($script:runs) | Set-Content -LiteralPath $manifestPath -Encoding utf8
}
if($Mode -eq 'Boundary') {
    # Full capacity is for the recorded 1920x1017 baseline. Renderer clamps the
    # request to actual capacity, which is recorded in the validation report.
    foreach($count in @(0,1,63,64,65,1952640)) {
        Invoke-ComparisonRun "boundary-$count" @('-smaaRecoveredSourceProfile','3','-smaaCandidateForcedCount',"$count",'-smaaOriginalFourCapture','"0 4 24"') $true
    }
}
elseif($Mode -eq 'Quality') {
    foreach($scene in $Scenes) {
        Invoke-ComparisonRun "$scene-spatial-control" @('-smaaCameraMotionSingleModeCapture',"`"$scene flythrough-wide-yaw-360 O-1X 0 $QualityFrames 60`"") $true
        foreach($profile in 0..3) {
            Invoke-ComparisonRun "$scene-profile-$profile" @('-smaaRecoveredSourceProfile',"$profile",'-smaaRecoveredSourceCapture',"`"$scene flythrough-wide-yaw-360 O-ET2X-R 0 $QualityFrames 60`"") $true
        }
    }
}
elseif($Mode -eq 'Masks') {
    foreach($scene in $Scenes) {
        foreach($profile in 0..1) {
            Invoke-ComparisonRun "$scene-mask-$profile" @('-smaaRecoveredSourceProfile',"$profile",'-smaaTemporalDebugView','2','-smaaRecoveredSourceCapture',"`"$scene flythrough-wide-yaw-360 O-ET2X-R 0 $QualityFrames 60`"") $true
        }
    }
}
else {
    foreach($scene in $Scenes) {
        Invoke-ComparisonRun "$scene-paired-benchmark" @('-smaaRecoveredSourcePerformanceBenchmark',"`"$scene 0 300 4800 3`"") $false
    }
}
