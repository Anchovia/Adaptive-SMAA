param(
    [ValidateSet('bistro','minecraft')][string] $Scene='bistro',
    [string] $OutputRoot='D:/SMAAResearchCaptures/native-first-pass-edge-20260930'
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$doc=Join-Path $root 'Docs/Native-FirstPass-Edge-Visuals'
New-Item -ItemType Directory -Path $doc -Force | Out-Null
$receipt=Join-Path $doc "$Scene-run.json"
if(Test-Path -LiteralPath $receipt){throw 'Run receipt already exists; do not overwrite'}
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'CMAA2 already running'}
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$hash=(Get-FileHash -LiteralPath $exe).Hash
$settings=Join-Path $root 'Projects/CMAA2/ApplicationSettings.xml'
$content=[IO.File]::ReadAllText($settings)
if(([regex]::Matches($content,'<SceneChoice>\d+</SceneChoice>')).Count -ne 1){throw 'Unexpected scene settings'}
$sceneIndex=if($Scene -eq 'bistro'){0}else{2}
[IO.File]::WriteAllText($settings,[regex]::Replace($content,'<SceneChoice>\d+</SceneChoice>',"<SceneChoice>$sceneIndex</SceneChoice>"))
$started=[DateTime]::UtcNow.ToString('o')
$arguments=@('-smaaNativeFirstPassEdgeCapture',$Scene,$OutputRoot)
$output=& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 600
$pass=$output | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass){throw 'Missing clean completion'}
$report=($pass -split 'report=',2)[1].Trim()
if((Get-Content -LiteralPath $report -Raw) -notmatch 'Aggregate: PASS'){throw 'Aggregate PASS missing'}
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed'}
[pscustomobject]@{scene=$Scene;arguments=$arguments;window='hidden';timeout_seconds=600;
    started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');
    executable_sha256=$hash;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash;
    bootstrap_scene_index=$sceneIndex;scope='Read native final RG only, unchanged frame rendering; no timing result'} |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receipt -Encoding utf8
Write-Output $pass
