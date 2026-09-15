param(
    [ValidateSet('Short','Quality','Masks','Benchmark')][string]$Mode='Short',
    [string]$Manifest='tmp/recovered-sharpen-segment/runs.json'
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$shader=Join-Path $repo 'Projects/CMAA2/SMAA/RecoveredTSCMAAUtility.hlsl'
$settings=Join-Path $repo 'Projects/CMAA2/ApplicationSettings.xml'
$bench=Join-Path $repo 'Projects/CMAA2/AutoBench'
$manifestPath=Join-Path $repo $Manifest
[IO.Directory]::CreateDirectory((Split-Path $manifestPath -Parent)) | Out-Null
$runs=@()
if(Test-Path $manifestPath){$runs=@(Get-Content -Raw $manifestPath | ConvertFrom-Json)}
$names=@('Sharpen-Component','NoSharpen-Component','Sharpen-Segment','NoSharpen-Segment')
$shaderOriginal=[IO.File]::ReadAllBytes($shader);$source=[IO.File]::ReadAllText($shader)
$settingsOriginal=[IO.File]::ReadAllBytes($settings);$settingsText=[IO.File]::ReadAllText($settings)
if(-not $source.Contains('#define SMAA_RECOVERED_SIGNED_CHROMA 0') -or -not $source.Contains('#define SMAA_RECOVERED_YCOCG_CLAMP 0')){throw 'Expected both clipping switches default Off'}
if(-not $source.Contains('#define SMAA_RECOVERED_DISABLE_SHARPEN 0') -or -not $source.Contains('#define SMAA_RECOVERED_SEGMENT_CLIP 0')){throw 'Expected new switches default Off'}
try {
    foreach($scene in @('bistro','minecraft')) {
        $pairs=if($Mode-eq 'Benchmark'){@(1,2,3)}else{@(0)}
        foreach($pair in $pairs) {
            $variants=if($Mode-eq 'Benchmark'){if($pair-eq 2){@(3,0)}else{@(0,3)}}else{@(0,1,2,3)}
            foreach($variant in $variants) {
                $label="$scene-$Mode-$($names[$variant])-pair-$pair"
                if(@($runs | Where-Object {$_.label-eq $label -and $_.status-eq 'PASS'}).Count-eq 1){continue}
                if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count-ne 0){throw 'Demo active before variant switch'}
                $disable=$variant-band 1;$segment=$variant-shr 1
                $changed=$source.Replace('#define SMAA_RECOVERED_SIGNED_CHROMA 0','#define SMAA_RECOVERED_SIGNED_CHROMA 1').Replace('#define SMAA_RECOVERED_YCOCG_CLAMP 0','#define SMAA_RECOVERED_YCOCG_CLAMP 1').Replace('#define SMAA_RECOVERED_DISABLE_SHARPEN 0',"#define SMAA_RECOVERED_DISABLE_SHARPEN $disable").Replace('#define SMAA_RECOVERED_SEGMENT_CLIP 0',"#define SMAA_RECOVERED_SEGMENT_CLIP $segment")
                [IO.File]::WriteAllText($shader,$changed,[Text.UTF8Encoding]::new($false))
                $startup=$settingsText -replace '<SceneChoice>\d+</SceneChoice>','<SceneChoice>0</SceneChoice>'
                [IO.File]::WriteAllText($settings,$startup,[Text.UTF8Encoding]::new($false))
                $args=@('-smaaRecoveredSourceProfile','3','-smaaRecoveredSourceIntegratedCandidates','1','-smaaCandidateStatisticsReadback','0')
                if($Mode-eq 'Benchmark'){
                    $args=@('-smaaIntegratedSourcePerformanceBenchmark',"`"$scene 0 300 4800 1`"")
                } else {
                    $frames=if($Mode-eq 'Quality'){480}else{12}
                    if($Mode-eq 'Masks'){$args+=@('-smaaTemporalDebugView','2')}
                    $args+=@('-smaaRecoveredSourceCapture',"`"$scene flythrough-wide-yaw-360 O-ET2X-R 0 $frames 60`"")
                }
                $before=@(Get-ChildItem $bench -Directory | ForEach-Object Name)
                $record=[ordered]@{label=$label;scene=$scene;mode=$Mode;variant=$names[$variant];signed_chroma=1;ycocg_clamp=1;disable_sharpen=$disable;segment_clip=$segment;pair=$pair;
                    semantic_id="O-ET2X-R-SourceIntegrated-$($names[$variant])";arguments=$args;window=$(if($Mode-eq 'Benchmark'){'visible'}else{'hidden'});
                    exe_sha256=(Get-FileHash (Join-Path $repo 'Projects/CMAA2/CMAA2.exe')).Hash;
                    utility_sha256=(Get-FileHash $shader).Hash;utility_source=$changed;
                    candidate_sha256=(Get-FileHash (Join-Path $repo 'Projects/CMAA2/SMAA/RecoveredTSCMAACandidate.hlsl')).Hash}
                Write-Output "Starting $label"
                $execution=@(& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $args -TimeoutSeconds 600 -Hidden:($Mode-ne 'Benchmark'))
                $execution | ForEach-Object {Write-Output $_}
                if(($execution -join "`n") -notmatch '\(PID (\d+)\)'){throw 'Missing clean runner process identity'}
                $record.process_id=[int]$Matches[1]
                $new=@(Get-ChildItem $bench -Directory | Where-Object {$_.Name -notin $before})
                if($new.Count-ne 1){throw 'Expected exactly one new result directory'}
                $record.report=$new[0].FullName;$record.status='PASS'
                Copy-Item (Join-Path $repo 'Projects/CMAA2/log.txt') (Join-Path $new[0].FullName 'clipping-execution.log')
                $runs+=$record
                ConvertTo-Json -Depth 8 -InputObject @($runs) | Set-Content -LiteralPath $manifestPath -Encoding utf8
            }
        }
    }
} finally {
    [IO.File]::WriteAllBytes($shader,$shaderOriginal)
    [IO.File]::WriteAllBytes($settings,$settingsOriginal)
}
