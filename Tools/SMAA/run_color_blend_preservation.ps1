param(
    [ValidateSet('Capture','Diagnostic','Smoke','Benchmark')][string]$Phase='Capture',
    [ValidateSet('bistro','minecraft')][string]$Scene='bistro',
    [Parameter(Mandatory=$true)][string]$Label,
    [string]$OutputRoot='D:\SMAAResearchCaptures\c17-cleanup-20261016',
    [string]$RetryReason=''
)
# One clean CMAA2 process per command for the case-17 output-preservation harness.
# Records executable, renderer source and report hashes for every completed run.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$receipt=Join-Path $root 'tmp/color-blend-preservation-runs.json'
if(!(Test-Path -LiteralPath (Split-Path $receipt))){New-Item -ItemType Directory -Path (Split-Path $receipt)|Out-Null}
$hash=(Get-FileHash -LiteralPath $exe).Hash
$sources=@{}
foreach($file in Get-ChildItem -LiteralPath (Join-Path $root 'Projects/CMAA2/SMAA') -File | Where-Object {$_.Extension -in '.cpp','.h','.hlsl','.hlsli'}){
    $sources['Projects/CMAA2/SMAA/'+$file.Name]=(Get-FileHash -LiteralPath $file.FullName).Hash
}
$harness=(Get-FileHash -LiteralPath (Join-Path $root 'Projects/CMAA2/ColorBlendPreservation.inl')).Hash
$commit=(& git -C $root rev-parse HEAD).Trim()
$dirty=@(& git -C $root status --porcelain --untracked-files=no -- Projects/CMAA2).Count -ne 0
$records=@()
if(Test-Path -LiteralPath $receipt){$records=@(Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json)}
if(@($records | Where-Object {$_.scene -eq $Scene -and $_.phase -eq $Phase -and $_.label -eq $Label}).Count -and !$RetryReason){throw 'Label already recorded; explicit retry reason required'}
if($Phase -eq 'Benchmark' -and !@($records | Where-Object {$_.scene -eq $Scene -and $_.phase -eq 'Smoke' -and $_.executable_sha256 -eq $hash}).Count){throw 'Same-binary smoke required before benchmark'}
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Existing CMAA2 process; no new run started'}
$settings=Join-Path $root 'Projects/CMAA2/ApplicationSettings.xml'
$content=[System.IO.File]::ReadAllText($settings)
if(([regex]::Matches($content,'<SceneChoice>\d+</SceneChoice>')).Count -ne 1){throw 'Unexpected initial scene settings'}
$sceneIndex=if($Scene -eq 'bistro'){0}else{2}
$content=[regex]::Replace($content,'<SceneChoice>\d+</SceneChoice>',"<SceneChoice>$sceneIndex</SceneChoice>")
$content=[regex]::Replace($content,'<CurrentAAOption>\d+</CurrentAAOption>','<CurrentAAOption>0</CurrentAAOption>')
[System.IO.File]::WriteAllText($settings,$content)
$output=Join-Path $OutputRoot $Label
New-Item -ItemType Directory -Force -Path $output | Out-Null
$started=[DateTime]::UtcNow.ToString('o')
$arguments=@("-smaaColorBlendPreservation$Phase",$Scene,$output)
$autoBench=Join-Path $root 'Projects/CMAA2/AutoBench'
$reportsBefore=@(Get-ChildItem -LiteralPath $autoBench -Recurse -File -Filter '*_results.csv' -ErrorAction SilentlyContinue | ForEach-Object {$_.FullName})
$result=& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 1200
$pass=$result | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass -and $Phase -eq 'Diagnostic'){
    # run_clean_cmaa2 only collects reports for *Test/*Capture/*Smoke/*Benchmark commands.
    $pass=$result | Where-Object {$_ -match '^PASS: clean CMAA2 process exited normally'} | Select-Object -Last 1
    $new=@(Get-ChildItem -LiteralPath $autoBench -Recurse -File -Filter '*_results.csv' | Where-Object {$reportsBefore -notcontains $_.FullName})
    if(!$pass -or $new.Count -ne 1){throw 'No single new Diagnostic report'}
    $pass="$pass; report=$($new[0].FullName)"
}
if(!$pass){throw 'No completed result'}
$report=($pass -split 'report=',2)[1].Trim()
$text=Get-Content -LiteralPath $report -Raw
if($text -notmatch 'Aggregate: PASS'){throw 'Aggregate PASS missing'}
if($text -match '(?im)^\s*Aggregate[^\r\n]*\bFAIL\b' -or $text -match '(?im),\s*FAIL\s*(?:,|$)'){throw "Report contains a failed check: $report"}
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed during execution'}
$captureRoot=([regex]::Match($text,'capture_root,\s*([^,\r\n]+)')).Groups[1].Value.Trim()
$records += [pscustomobject]@{label=$Label;scene=$Scene;phase=$Phase;window='hidden';arguments=$arguments;scene_bootstrap=$sceneIndex;retry_reason=$RetryReason;
    git_head=$commit;renderer_dirty=$dirty;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');executable_sha256=$hash;harness_sha256=$harness;
    renderer_sha256=$sources;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash;capture_root=$captureRoot}
ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $receipt -Encoding utf8
Write-Output $pass
