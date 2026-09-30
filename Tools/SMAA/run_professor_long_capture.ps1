param(
    [ValidateSet('audit','1','2','3','5')][string]$Case='audit',
    [ValidateSet('bistro','minecraft')][string]$Scene='bistro',
    [string]$OutputRoot='D:/SMAAResearchCaptures/professor-eight-case-20261001'
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$method=Get-Content -LiteralPath (Join-Path $root 'Docs/Professor-Long-Capture/method.json') -Raw | ConvertFrom-Json
if($method.case -ne $Case){throw 'Wrong capture branch'}
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Existing CMAA2 process'}
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$hash=(Get-FileHash -LiteralPath $exe).Hash
$settings=Join-Path $root 'Projects/CMAA2/ApplicationSettings.xml'
$content=[System.IO.File]::ReadAllText($settings)
if(([regex]::Matches($content,'<SceneChoice>\d+</SceneChoice>')).Count -ne 1){throw 'Unexpected initial scene settings'}
$sceneIndex=if($Scene -eq 'bistro'){0}else{2}
[System.IO.File]::WriteAllText($settings,[regex]::Replace($content,'<SceneChoice>\d+</SceneChoice>',"<SceneChoice>$sceneIndex</SceneChoice>"))
$command=if($Case -eq 'audit'){'-smaaEdgePersistenceCostAuditCapture'}else{'-smaaStencilLifecycleCapture'}
$started=[DateTime]::UtcNow.ToString('o')
$output=& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments @($command,$Scene,$OutputRoot) -Hidden -TimeoutSeconds 1200
$pass=$output | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass){throw 'No completed result'}
$report=($pass -split 'report=',2)[1].Trim()
if((Get-Content -LiteralPath $report -Raw) -notmatch 'Aggregate: PASS'){throw 'Aggregate PASS missing'}
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed'}
$record=[pscustomobject]@{case=$Case;scene=$Scene;branch=$method.branch;base=$method.base;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');executable_sha256=$hash;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash;output_root=$OutputRoot;clean_process='PASS';frames=480}
$receipt=Join-Path $root "tmp/professor-case$Case-$Scene-receipt.json"
$record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receipt -Encoding utf8
Write-Output $pass
