param(
    [Parameter(Mandatory=$true)][ValidateSet('Snapshot','Regression','Boundary','ShortQuality','Quality','Masks','Smoke','Benchmark')][string]$Mode,
    [ValidateSet('bistro','minecraft')][string[]]$Scenes=@('bistro','minecraft'),
    [string]$Manifest='tmp/integrated-source-runs.json'
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$bench=Join-Path $repo 'Projects/CMAA2/AutoBench'
$manifestPath=[IO.Path]::GetFullPath((Join-Path $repo $Manifest))
New-Item -ItemType Directory -Force -Path (Split-Path $manifestPath) | Out-Null
$runs=@()
if(Test-Path -LiteralPath $manifestPath) { $runs=@(Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json) }
function Invoke-IntegratedRun([string]$label,[string[]]$demoArguments,[bool]$hidden=$true) {
    $before=@(Get-ChildItem -LiteralPath $bench -Directory | ForEach-Object Name)
    $exeHash=(Get-FileHash -LiteralPath (Join-Path $repo 'Projects/CMAA2/CMAA2.exe')).Hash
    & (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $demoArguments -TimeoutSeconds 1200 -Hidden:$hidden
    $new=@(Get-ChildItem -LiteralPath $bench -Directory | Where-Object { $_.Name -notin $before })
    if($new.Count -ne 1) { throw "Expected exactly one report directory for $label" }
    Copy-Item -LiteralPath (Join-Path $repo 'Projects/CMAA2/log.txt') -Destination (Join-Path $new[0].FullName 'integrated-source-execution.log')
    $script:runs += [ordered]@{label=$label;arguments=$demoArguments;report=$new[0].FullName;exe_sha256=$exeHash;window=$(if($hidden){'hidden'}else{'visible'});status='PASS'}
    ConvertTo-Json -Depth 8 -InputObject @($script:runs) | Set-Content -LiteralPath $manifestPath -Encoding utf8
}
switch($Mode) {
    'Snapshot' { Invoke-IntegratedRun 'snapshot' @('-smaaIntegratedSourceSnapshotTest') }
    'Regression' {
        Invoke-IntegratedRun 'default-eight-regression' @('-smaaEightCaseCapture','"0 12 60"')
        Invoke-IntegratedRun 'lifecycle' @('-smaaTemporalLifecycleTest')
        Invoke-IntegratedRun 'integrated-feedback' @('-smaaRecoveredSourceProfile','3','-smaaRecoveredSourceIntegratedCandidates','1','-smaaTemporalFeedbackTest')
    }
    'Boundary' {
        foreach($count in @(0,1,63,64,65,1952640)) {
            Invoke-IntegratedRun "boundary-$count" @('-smaaRecoveredSourceProfile','3','-smaaRecoveredSourceIntegratedCandidates','1','-smaaCandidateForcedCount',"$count",'-smaaOriginalFourCapture','"0 4 24"')
        }
    }
    {$_ -in 'ShortQuality','Quality','Masks'} {
        $frames=if($Mode -eq 'Quality'){480}else{12}
        foreach($scene in $Scenes) {
            if($Mode -ne 'Masks') {
                foreach($id in @('O-1X','O-T2X-R')) {
                    Invoke-IntegratedRun "$scene-$Mode-$id" @('-smaaCameraMotionSingleModeCapture',"`"$scene flythrough-wide-yaw-360 $id 0 $frames 60`"")
                }
            }
            foreach($integrated in 0..1) {
                $extra=if($Mode -eq 'Masks'){@('-smaaTemporalDebugView','2')}else{@()}
                Invoke-IntegratedRun "$scene-$Mode-source-$integrated" (@('-smaaRecoveredSourceProfile','3','-smaaRecoveredSourceIntegratedCandidates',"$integrated")+$extra+@('-smaaRecoveredSourceCapture',"`"$scene flythrough-wide-yaw-360 O-ET2X-R 0 $frames 60`""))
            }
        }
    }
    {$_ -in 'Smoke','Benchmark'} {
        $values=if($Mode -eq 'Benchmark'){'0 300 4800 3'}else{'0 60 180 1'}
        foreach($scene in $Scenes) {
            Invoke-IntegratedRun "$scene-$Mode" @("-smaaIntegratedSourcePerformance$Mode","`"$scene $values`"") $false
        }
    }
}
