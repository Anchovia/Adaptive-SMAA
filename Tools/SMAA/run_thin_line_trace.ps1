param(
    [ValidateSet('Capture','Smoke')][string] $Phase='Smoke',
    [ValidateSet('bistro','minecraft')][string] $Scene='bistro',
    [string] $OutputRoot='D:/SMAAResearchCaptures/thin-line-trace-20261001'
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$doc=Join-Path $root 'Docs/Thin-Line-Trace'
$receipt=Join-Path $doc "$Scene-$($Phase.ToLower())-run.json"
if(Test-Path -LiteralPath $receipt){throw 'Completed receipt exists; do not overwrite'}
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Existing CMAA2 process'}
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$hash=(Get-FileHash -LiteralPath $exe).Hash
$audit=Get-Content -LiteralPath (Join-Path $doc 'source-audit.json') -Raw | ConvertFrom-Json
if($audit.validation -ne 'PASS' -or $audit.executable_sha256 -ne $hash){throw 'Missing current executable audit'}
$settings=Join-Path $root 'Projects/CMAA2/ApplicationSettings.xml'
$content=[System.IO.File]::ReadAllText($settings)
if(([regex]::Matches($content,'<SceneChoice>\d+</SceneChoice>')).Count -ne 1){throw 'Unexpected startup scene settings'}
$sceneIndex=if($Scene -eq 'bistro'){0}else{2}
[System.IO.File]::WriteAllText($settings,[regex]::Replace($content,'<SceneChoice>\d+</SceneChoice>',"<SceneChoice>$sceneIndex</SceneChoice>"))
$started=[DateTime]::UtcNow.ToString('o')
$arguments=@("-smaaThinLineTrace$Phase",$Scene,$OutputRoot)
$output=& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 600
$pass=$output | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass){throw 'No completed clean-process report'}
$report=($pass -split 'report=',2)[1].Trim()
if((Get-Content -LiteralPath $report -Raw) -notmatch 'Aggregate: PASS'){throw 'Aggregate PASS missing'}
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed during run'}
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Residual CMAA2 process'}
[pscustomobject]@{scene=$Scene;phase=$Phase;window='hidden';arguments=$arguments;timeout_seconds=600;bootstrap_scene_index=$sceneIndex;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');executable_sha256=$hash;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash;scope='Raw inputs and unchanged output; no performance result'} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receipt -Encoding utf8
Write-Output $pass
