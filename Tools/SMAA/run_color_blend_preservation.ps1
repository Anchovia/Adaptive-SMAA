param(
    [ValidateSet('Preservation','Optimization')][string]$Harness='Preservation',
    [ValidateSet('Capture','Diagnostic','Profile','Smoke','Benchmark','SpatialCapture')][string]$Phase='Capture',
    [ValidateSet('bistro','minecraft')][string]$Scene='bistro',
    [Parameter(Mandatory=$true)][string]$Label,
    [string]$OutputRoot='D:\SMAAResearchCaptures\c17-cleanup-20261016',
    [string]$RetryReason='',
    [string]$WorktreeRoot='',
    # Formal timing: an OS-visible window (no -Hidden) with the given client size; the report must have it.
    [switch]$Visible,
    [ValidateRange(64,8192)][int]$ClientWidth=1920,
    [ValidateRange(64,8192)][int]$ClientHeight=1061,
    # Window position (outer rectangle, pixels); -1 lets the application place it.
    [int]$WindowX=-1,
    [int]$WindowY=-1,
    # vaFullscreenState: 1 Windowed, 2 Fullscreen (exclusive), 3 Fullscreen Borderless. The report must show it.
    [ValidateSet(1,2,3)][int]$FullscreenState=1
)
# One clean CMAA2 process per command for the case-17 preservation/optimization harnesses.
# Records executable, renderer source and report hashes for every completed run.
$ErrorActionPreference='Stop'
$root=if($WorktreeRoot){(Resolve-Path -LiteralPath $WorktreeRoot).Path}else{(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path}
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$receipt=Join-Path $root 'tmp/color-blend-preservation-runs.json'
if(!(Test-Path -LiteralPath (Split-Path $receipt))){New-Item -ItemType Directory -Path (Split-Path $receipt)|Out-Null}
$hash=(Get-FileHash -LiteralPath $exe).Hash
$sources=@{}
foreach($file in Get-ChildItem -LiteralPath (Join-Path $root 'Projects/CMAA2/SMAA') -File | Where-Object {$_.Extension -in '.cpp','.h','.hlsl','.hlsli'}){
    $sources['Projects/CMAA2/SMAA/'+$file.Name]=(Get-FileHash -LiteralPath $file.FullName).Hash
}
$harnessFile=Join-Path $root "Projects/CMAA2/ColorBlend$Harness.inl"
if(($Harness -eq 'Preservation' -and $Phase -in 'Profile','SpatialCapture') -or ($Harness -eq 'Optimization' -and $Phase -eq 'Diagnostic')){throw "Phase $Phase is not defined for the $Harness harness"}
$harnessHash=(Get-FileHash -LiteralPath $harnessFile).Hash
# Trust only this selected worktree for this invocation, without changing global
# Git settings when the sandbox user has a different SID from the owner.
$gitOptions=@('-c','gc.auto=0','-c',"safe.directory=$($root.Replace('\','/'))",'-C',$root)
$commitLines=@(& git @gitOptions rev-parse HEAD)
if($LASTEXITCODE -ne 0 -or $commitLines.Count -ne 1){throw 'Cannot identify worktree commit'}
$commit=$commitLines[0].Trim()
$dirtyLines=@(& git @gitOptions status --porcelain --untracked-files=no -- Projects/CMAA2)
if($LASTEXITCODE -ne 0){throw 'Cannot identify renderer working-tree state'}
$dirty=$dirtyLines.Count -ne 0
$records=@()
if(Test-Path -LiteralPath $receipt){$records=@(Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json)}
$recordHarness={param($r) if($r.harness){$r.harness}else{'Preservation'}}
if(@($records | Where-Object {$_.scene -eq $Scene -and $_.phase -eq $Phase -and $_.label -eq $Label -and (& $recordHarness $_) -eq $Harness}).Count -and !$RetryReason){throw 'Label already recorded; explicit retry reason required'}
if($Phase -eq 'Benchmark' -and !@($records | Where-Object {$_.scene -eq $Scene -and $_.phase -eq 'Smoke' -and $_.executable_sha256 -eq $hash -and (& $recordHarness $_) -eq $Harness}).Count){throw 'Same-binary smoke required before benchmark'}
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Existing CMAA2 process; no new run started'}
$gpuBefore=@(& nvidia-smi --query-gpu=name,driver_version,pstate,utilization.gpu,memory.used --format=csv,noheader)
if($LASTEXITCODE -ne 0){throw 'Cannot verify GPU state before execution'}
$gpuProcessesBefore=@(& nvidia-smi)
if($LASTEXITCODE -ne 0){throw 'Cannot inspect GPU processes before execution'}
$settings=Join-Path $root 'Projects/CMAA2/ApplicationSettings.xml'
$content=[System.IO.File]::ReadAllText($settings)
# The excluded opt-c run persisted a resized window. Restore the established
# cleanup capture geometry before launch; the in-process size check still guards
# against changes during the run. Windowed is vaFullscreenState value 1.
$windowSettings=[ordered]@{WindowPositionX=$WindowX;WindowPositionY=$WindowY;WindowClientSizeX=$ClientWidth;WindowClientSizeY=$ClientHeight;FullscreenState=$FullscreenState}
foreach($entry in $windowSettings.GetEnumerator()){
    $pattern="<$($entry.Key)>-?\d+</$($entry.Key)>"
    if(([regex]::Matches($content,$pattern)).Count -ne 1){throw "Unexpected window setting: $($entry.Key)"}
    $content=[regex]::Replace($content,$pattern,"<$($entry.Key)>$($entry.Value)</$($entry.Key)>")
}
if(([regex]::Matches($content,'<SceneChoice>\d+</SceneChoice>')).Count -ne 1){throw 'Unexpected initial scene settings'}
$sceneIndex=if($Scene -eq 'bistro'){0}else{2}
$content=[regex]::Replace($content,'<SceneChoice>\d+</SceneChoice>',"<SceneChoice>$sceneIndex</SceneChoice>")
$content=[regex]::Replace($content,'<CurrentAAOption>\d+</CurrentAAOption>','<CurrentAAOption>0</CurrentAAOption>')
[System.IO.File]::WriteAllText($settings,$content)
$output=Join-Path $OutputRoot $Label
New-Item -ItemType Directory -Force -Path $output | Out-Null
$started=[DateTime]::UtcNow.ToString('o')
$arguments=@("-smaaColorBlend$Harness$Phase",$Scene,$output)
$autoBench=Join-Path $root 'Projects/CMAA2/AutoBench'
$reportsBefore=@(Get-ChildItem -LiteralPath $autoBench -Recurse -File -Filter '*_results.csv' -ErrorAction SilentlyContinue | ForEach-Object {$_.FullName})
$cleanRunner=Join-Path $root 'Tools/SMAA/run_clean_cmaa2.ps1'
$result=if($Visible){& $cleanRunner -CMAA2Arguments $arguments -TimeoutSeconds 1200}else{& $cleanRunner -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 1200}
$pass=$result | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass -and $Phase -in 'Diagnostic','Profile'){
    # run_clean_cmaa2 only collects reports for *Test/*Capture/*Smoke/*Benchmark commands.
    $pass=$result | Where-Object {$_ -match '^PASS: clean CMAA2 process exited normally'} | Select-Object -Last 1
    $new=@(Get-ChildItem -LiteralPath $autoBench -Recurse -File -Filter '*_results.csv' | Where-Object {$reportsBefore -notcontains $_.FullName})
    if(!$pass -or $new.Count -ne 1){throw "No single new $Phase report"}
    $pass="$pass; report=$($new[0].FullName)"
}
if(!$pass){throw 'No completed result'}
$report=($pass -split 'report=',2)[1].Trim()
$text=Get-Content -LiteralPath $report -Raw
if($text -notmatch 'Aggregate: PASS'){throw 'Aggregate PASS missing'}
if($text -match '(?im)^\s*Aggregate[^\r\n]*\bFAIL\b' -or $text -match '(?im),\s*FAIL\s*(?:,|$)'){throw "Report contains a failed check: $report"}
if($text -notmatch "Resolution:\s*$ClientWidth\s*x\s*$ClientHeight\b"){throw "Report does not have the fixed output resolution ${ClientWidth}x${ClientHeight}: $report"}
$fullscreenLabel=@{1='Windowed';2='Fullscreen';3='Fullscreen Borderless'}[$FullscreenState]
if($text -notmatch "(?m)^Fullscreen:\s*$([regex]::Escape($fullscreenLabel))\s*$"){throw "Report does not have the requested window state ${fullscreenLabel}: $report"}
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed during execution'}
$captureRoot=([regex]::Match($text,'capture_root,\s*([^,\r\n]+)')).Groups[1].Value.Trim()
$records += [pscustomobject]@{harness=$Harness;label=$Label;scene=$Scene;phase=$Phase;window=$(if($Visible){'visible'}else{'hidden'});expected_resolution=@($ClientWidth,$ClientHeight);window_position=@($WindowX,$WindowY);fullscreen_state=$fullscreenLabel;arguments=$arguments;scene_bootstrap=$sceneIndex;retry_reason=$RetryReason;
    worktree_root=$root;gpu_before=$gpuBefore;gpu_processes_before=$gpuProcessesBefore;
    git_head=$commit;renderer_dirty=$dirty;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');executable_sha256=$hash;harness_sha256=$harnessHash;
    renderer_sha256=$sources;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash;capture_root=$captureRoot}
ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $receipt -Encoding utf8
Write-Output $pass
