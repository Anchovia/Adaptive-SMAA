param(
    [ValidateSet('Capture','Smoke','Benchmark')][string] $Phase='Capture',
    [ValidateSet('bistro','minecraft')][string] $Scene='bistro',
    [string] $OutputRoot='D:/SMAAResearchCaptures/stencil-lifecycle-20260930'
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$doc=Join-Path $root 'Docs/Stencil-Lifecycle-Refresh'
$config=Get-Content -LiteralPath (Join-Path $doc 'case.json') -Raw | ConvertFrom-Json
$receipt=Join-Path $root "tmp/stencil-lifecycle-case$($config.case)-runs.json"
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$hash=(Get-FileHash -LiteralPath $exe).Hash
$records=@()
if(Test-Path -LiteralPath $receipt){$records=@(Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json)}
if(@($records | Where-Object {$_.scene -eq $Scene -and $_.phase -eq $Phase}).Count){throw 'Completed run already recorded; do not overwrite'}
foreach($gate in @('source-audit') + $(if($Phase -ne 'Capture'){@("$Scene-capture")}else{@()}) + $(if($Phase -eq 'Benchmark'){@("$Scene-smoke")}else{@()})){
    $path=Join-Path $doc "$gate.json"
    if(!(Test-Path -LiteralPath $path)){throw "Missing gate: $gate"}
    $data=Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if($data.validation -ne 'PASS' -or $data.executable_sha256 -ne $hash){throw "Failed or different executable gate: $gate"}
}
$started=[DateTime]::UtcNow.ToString('o')
$arguments=@("-smaaStencilLifecycle$Phase",$Scene,$OutputRoot)
$output=& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 1200
$pass=$output | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass){throw 'No completed result'}
$report=($pass -split 'report=',2)[1].Trim()
if((Get-Content -LiteralPath $report -Raw) -notmatch 'Aggregate: PASS'){throw 'Aggregate PASS missing'}
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed'}
$records += [pscustomobject]@{case=$config.case;branch=$config.branch;scene=$Scene;phase=$Phase;window='hidden';arguments=$arguments;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');executable_sha256=$hash;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash}
ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $receipt -Encoding utf8
Write-Output $pass
