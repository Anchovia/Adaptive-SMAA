param(
    [ValidateSet('Test','Capture','Smoke','Benchmark','ProfileSmoke','ProfileBenchmark')][string]$Phase='Test',
    [ValidateSet('bistro','minecraft')][string]$Scene='bistro',
    [string]$OutputRoot='C:/Users/USER/Desktop/research/tmp/worktrees/standard-t2x-reuse/tmp/spatial-cost-captures',
    [string]$RetryReason=''
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$receipt=Join-Path $root 'tmp/edge-persistence-spatial-cost-runs.json'
$hash=(Get-FileHash -LiteralPath $exe).Hash
$shaderPaths=@('Projects/CMAA2/SMAA/FirstEdgeStencil.hlsl','Projects/CMAA2/SMAA/PersistenceEdgeStencil.hlsl','Projects/CMAA2/SMAA/SMAAWrapper.hlsl','Projects/CMAA2/SMAA/SMAA.hlsl')
$shaderHashes=@{}
foreach($shaderPath in $shaderPaths){$shaderHashes[$shaderPath]=(Get-FileHash -LiteralPath (Join-Path $root $shaderPath)).Hash}
$records=@()
if(Test-Path -LiteralPath $receipt){$records=@(Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json)}
if(@($records | Where-Object {$_.scene -eq $Scene -and $_.phase -eq $Phase -and $_.executable_sha256 -eq $hash}).Count -and !$RetryReason){throw 'Completed run already recorded for this binary; explicit retry reason required'}
if($Phase -like '*Benchmark' -and !@($records | Where-Object {$_.scene -eq $Scene -and $_.phase -eq $Phase.Replace('Benchmark','Smoke') -and $_.executable_sha256 -eq $hash}).Count){throw 'Same-binary smoke required'}
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Existing CMAA2 process'}
$settings=Join-Path $root 'Projects/CMAA2/ApplicationSettings.xml'
$content=[System.IO.File]::ReadAllText($settings)
if(([regex]::Matches($content,'<SceneChoice>\d+</SceneChoice>')).Count -ne 1){throw 'Unexpected initial scene settings'}
$sceneIndex=if($Scene -eq 'bistro'){0}else{2}
[System.IO.File]::WriteAllText($settings,[regex]::Replace($content,'<SceneChoice>\d+</SceneChoice>',"<SceneChoice>$sceneIndex</SceneChoice>"))
# Start in AA-Off to avoid saved-mode resource initialization before the harness.
$content=[System.IO.File]::ReadAllText($settings)
$content=[regex]::Replace($content,'<CurrentAAOption>\d+</CurrentAAOption>','<CurrentAAOption>0</CurrentAAOption>')
[System.IO.File]::WriteAllText($settings,$content)
$started=[DateTime]::UtcNow.ToString('o')
$arguments=@("-smaaEdgePersistenceSpatialCost$Phase",$Scene,$OutputRoot)
$output=& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 1200
$pass=$output | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass){throw 'No completed result'}
$report=($pass -split 'report=',2)[1].Trim()
if((Get-Content -LiteralPath $report -Raw) -notmatch 'Aggregate: PASS'){throw 'Aggregate PASS missing'}
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed'}
foreach($shaderPath in $shaderPaths){if((Get-FileHash -LiteralPath (Join-Path $root $shaderPath)).Hash -ne $shaderHashes[$shaderPath]){throw 'Shader changed during execution'}}
$records += [pscustomobject]@{scene=$Scene;phase=$Phase;window='hidden';arguments=$arguments;scene_bootstrap=$sceneIndex;retry_reason=$RetryReason;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');executable_sha256=$hash;shader_sha256=$shaderHashes;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash}
ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $receipt -Encoding utf8
Write-Output $pass
