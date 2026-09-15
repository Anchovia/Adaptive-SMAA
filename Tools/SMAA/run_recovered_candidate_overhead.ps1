param(
    [ValidateSet('Verify','Paired')][string]$Mode='Verify',
    [string]$Manifest='tmp/recovered-candidate-reuse/overhead-runs.json'
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$shader=Join-Path $repo 'Projects/CMAA2/SMAA/SMAAWrapper.hlsl'
$candidate=Join-Path $repo 'Projects/CMAA2/SMAA/RecoveredTSCMAACandidate.hlsl'
$bench=Join-Path $repo 'Projects/CMAA2/AutoBench'
$manifestPath=Join-Path $repo $Manifest
$runs=@()
if(Test-Path -LiteralPath $manifestPath) { $runs=@(Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json) }
function Invoke-Run([string]$label,[string[]]$demoArguments,[bool]$hidden) {
    $before=@(Get-ChildItem -LiteralPath $bench -Directory | ForEach-Object Name)
    $record=[ordered]@{label=$label;arguments=$demoArguments;window=$(if($hidden){'hidden'}else{'visible'});
        exe_sha256=(Get-FileHash (Join-Path $repo 'Projects/CMAA2/CMAA2.exe')).Hash;
        shader_sha256=(Get-FileHash $shader).Hash;candidate_sha256=(Get-FileHash $candidate).Hash}
    & (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $demoArguments -TimeoutSeconds 600 -Hidden:$hidden
    $new=@(Get-ChildItem -LiteralPath $bench -Directory | Where-Object {$_.Name -notin $before})
    if($new.Count-ne 1) {throw 'Expected one new result directory'}
    $record.report=$new[0].FullName;$record.status='PASS'
    Copy-Item (Join-Path $repo 'Projects/CMAA2/log.txt') (Join-Path $new[0].FullName 'candidate-overhead-execution.log')
    $script:runs+= $record
    ConvertTo-Json -Depth 8 -InputObject @($script:runs) | Set-Content -LiteralPath $manifestPath -Encoding utf8
}
if($Mode-eq 'Verify') {
    foreach($scene in @('bistro','minecraft')) {
        # The existing full camera capture already forces readback Off.
        # Only the independently requested debug-mask path remains here.
        foreach($debug in @(2)) {
            $frames=12
            Invoke-Run "$scene-readback-off-debug-$debug" @('-smaaCandidateStatisticsReadback','0','-smaaRecoveredSourceProfile','3',
                '-smaaRecoveredSourceIntegratedCandidates','1','-smaaTemporalDebugView',"$debug",
                '-smaaRecoveredSourceCapture',"`"$scene flythrough-wide-yaw-360 O-ET2X-R 0 $frames 60`"") $true
        }
    }
    foreach($count in @(0,65,1952640)) {
        Invoke-Run "forced-readback-off-$count" @('-smaaCandidateStatisticsReadback','0','-smaaRecoveredSourceProfile','3',
            '-smaaRecoveredSourceIntegratedCandidates','1','-smaaCandidateForcedCount',"$count",
            '-smaaOriginalFourCapture','"0 4 24"') $true
    }
} else {
    # Both variants use the same executable. Only this shader compile switch
    # changes between independent processes; preserve source bytes in finally.
    $original=[IO.File]::ReadAllBytes($shader)
    $source=[IO.File]::ReadAllText($shader)
    $settingsPath=Join-Path $repo 'Projects/CMAA2/ApplicationSettings.xml'
    $settingsOriginal=[IO.File]::ReadAllBytes($settingsPath)
    $settingsText=[IO.File]::ReadAllText($settingsPath)
    if(-not $source.Contains('#define SMAA_RECOVERED_OPTIONAL_DIAGNOSTICS 1')) {throw 'Expected optimized shader default'}
    try {
        foreach($scene in @('bistro','minecraft')) {
            foreach($pair in 1..3) {
                $order=if($pair-eq 2){@(1,0)}else{@(0,1)}
                foreach($variant in $order) {
                    $label="$scene-pair-$pair-optional-$variant"
                    if(@($script:runs | Where-Object {$_.label-eq $label -and $_.status-eq 'PASS'}).Count-eq 1) {continue}
                    if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count-ne 0) {throw 'Demo running before shader switch'}
                    $current=$source.Replace('#define SMAA_RECOVERED_OPTIONAL_DIAGNOSTICS 1',"#define SMAA_RECOVERED_OPTIONAL_DIAGNOSTICS $variant")
                    [IO.File]::WriteAllText($shader,$current,[Text.UTF8Encoding]::new($false))
                    # Avoid rendering the user's persisted San Miguel scene
                    # before AutoBench selects its actual target scene.
                    # The measured scene/path/warm-up are still set by AutoBench.
                    $startup=$settingsText -replace '<SceneChoice>\d+</SceneChoice>','<SceneChoice>0</SceneChoice>'
                    [IO.File]::WriteAllText($settingsPath,$startup,[Text.UTF8Encoding]::new($false))
                    Invoke-Run $label @('-smaaIntegratedSourcePerformanceBenchmark',"`"$scene 0 300 4800 1`"") $false
                }
            }
        }
    } finally {
        [IO.File]::WriteAllBytes($shader,$original)
        [IO.File]::WriteAllBytes($settingsPath,$settingsOriginal)
    }
}
