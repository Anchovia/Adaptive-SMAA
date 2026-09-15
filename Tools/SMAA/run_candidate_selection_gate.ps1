param(
    [ValidateSet('Short','Quality','Masks','Smoke','Benchmark','Regression','Publication')][string]$Mode='Short',
    [ValidateSet('bistro','minecraft')][string[]]$Scenes=@('bistro','minecraft'),
    [string]$Manifest='tmp/candidate-selection-gate/runs.json'
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$settings=Join-Path $repo 'Projects/CMAA2/ApplicationSettings.xml'
$original=[IO.File]::ReadAllBytes($settings);$source=[IO.File]::ReadAllText($settings)
$manifestPath=Join-Path $repo $Manifest
[IO.Directory]::CreateDirectory((Split-Path $manifestPath -Parent)) | Out-Null
$runs=@()
if(Test-Path $manifestPath){$runs=@(Get-Content -Raw $manifestPath | ConvertFrom-Json)}
function Invoke-Gate([string]$label,[string[]]$demoArguments,[bool]$hidden=$true) {
    if(@($script:runs | Where-Object {$_.label-eq $label}).Count-ne 0){throw "Already recorded: $label"}
    if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count-ne 0){throw 'CMAA2 already running'}
    [IO.File]::WriteAllText($settings,($source -replace '<SceneChoice>\d+</SceneChoice>','<SceneChoice>0</SceneChoice>'),[Text.UTF8Encoding]::new($false))
    $hashes=[ordered]@{}
    foreach($file in @('CMAA2.exe','SMAA/SMAAWrapper.hlsl','SMAA/RecoveredTSCMAA.hlsl','SMAA/RecoveredTSCMAACandidate.hlsl','SMAA/RecoveredTSCMAAUtility.hlsl')) {
        $hashes[$file]=(Get-FileHash (Join-Path $repo "Projects/CMAA2/$file")).Hash
    }
    Write-Output "Starting $label"
    $execution=@(& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $demoArguments -TimeoutSeconds 600 -Hidden:$hidden)
    $execution | ForEach-Object {Write-Output $_}
    if(($execution -join "`n")-notmatch 'report=(.+_results.csv)'){throw 'Missing report'}
    $report=$Matches[1]
    if(($execution -join "`n")-notmatch '\(PID (\d+)\)'){throw 'Missing process identity'}
    $record=[ordered]@{label=$label;arguments=$demoArguments;report=(Split-Path $report -Parent);process_id=[int]$Matches[1];hashes=$hashes;window=$(if($hidden){'hidden'}else{'visible'});status='PASS'}
    Copy-Item (Join-Path $repo 'Projects/CMAA2/log.txt') (Join-Path $record.report 'candidate-selection-execution.log')
    $script:runs+=$record
    ConvertTo-Json -InputObject @($script:runs) -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
}
try {
    if($Mode-eq 'Publication') {
        Invoke-Gate 'material-publication-1' @('-smaaMaterialPublicationTest')
        Invoke-Gate 'material-publication-2' @('-smaaMaterialPublicationTest')
    } elseif($Mode-eq 'Regression') {
        Invoke-Gate 'default-eight' @('-smaaEightCaseCapture','"1 12 60"')
        Invoke-Gate 'source-candidate-document-feedback' @('-smaaRecoveredSourceProfile','1','-smaaRecoveredSourceIntegratedCandidates','1','-smaaTemporalFeedbackTest')
    } else {
        foreach($scene in $Scenes) {
            if($Mode-in @('Smoke','Benchmark')) {
                $values=if($Mode-eq 'Benchmark'){'0 300 4800 3'}else{'0 60 180 1'}
                Invoke-Gate "$scene-$Mode" @("-smaaCandidateSelectionPerformance$Mode","`"$scene $values`"") $false
            } else {
                $frames=if($Mode-eq 'Quality'){480}elseif($Mode-eq 'Masks'){120}else{12}
                if($Mode-ne 'Masks') {
                    foreach($id in @('O-1X','O-T2X-R')) {
                        Invoke-Gate "$scene-$Mode-$id" @('-smaaCameraMotionSingleModeCapture',"`"$scene flythrough-wide-yaw-360 $id 0 $frames 60`"")
                    }
                }
                foreach($profile in 0..1) {
                    $extra=if($Mode-eq 'Masks'){@('-smaaTemporalDebugView','2')}else{@()}
                    Invoke-Gate "$scene-$Mode-profile-$profile" (@('-smaaRecoveredSourceProfile',"$profile",'-smaaRecoveredSourceIntegratedCandidates','1','-smaaCandidateStatisticsReadback','0')+$extra+@('-smaaRecoveredSourceCapture',"`"$scene flythrough-wide-yaw-360 O-ET2X-R 0 $frames 60`""))
                }
            }
        }
    }
} finally {[IO.File]::WriteAllBytes($settings,$original)}
