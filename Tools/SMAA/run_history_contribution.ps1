param(
    [ValidateSet('bistro','minecraft')][string] $Scene='bistro',
    [string] $OutputRoot='D:/SMAAResearchCaptures/history-contribution-20260930'
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$config=Get-Content -LiteralPath (Join-Path $root 'Docs/Stencil-Lifecycle-Refresh/case.json') -Raw | ConvertFrom-Json
if($config.case -notin @(5,6)){throw 'Requires an independent corrected case 5 or 6 branch'}
$doc=Join-Path $root "Docs/History-Contribution/case$($config.case)"
New-Item -ItemType Directory -Path $doc -Force | Out-Null
$receipt=Join-Path $doc "$Scene-run.json"
if(Test-Path -LiteralPath $receipt){throw 'Completed run exists; preserve it'}
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'CMAA2 already running'}
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$hash=(Get-FileHash -LiteralPath $exe).Hash
$settings=Join-Path $root 'Projects/CMAA2/ApplicationSettings.xml'
$content=[IO.File]::ReadAllText($settings)
if(([regex]::Matches($content,'<SceneChoice>\d+</SceneChoice>')).Count -ne 1){throw 'Unexpected scene settings'}
$sceneIndex=if($Scene -eq 'bistro'){0}else{2}
[IO.File]::WriteAllText($settings,[regex]::Replace($content,'<SceneChoice>\d+</SceneChoice>',"<SceneChoice>$sceneIndex</SceneChoice>"))
$started=[DateTime]::UtcNow.ToString('o')
$arguments=@('-smaaHistoryContributionCapture',$Scene,$OutputRoot)
$output=& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 600
$pass=$output | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass){throw 'No clean completion'}
$report=($pass -split 'report=',2)[1].Trim()
if((Get-Content -LiteralPath $report -Raw) -notmatch 'Aggregate: PASS'){throw 'Aggregate PASS missing'}
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed'}
[pscustomobject]@{case=$config.case;scene=$Scene;arguments=$arguments;window='hidden';timeout_seconds=600;
    started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');
    executable_sha256=$hash;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash;
    bootstrap_scene_index=$sceneIndex;scope='GPU native history weight/current-color capture; no timing claim'} |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receipt -Encoding utf8
Write-Output $pass
