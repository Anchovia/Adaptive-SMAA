param(
    [ValidateSet('Capture','Smoke','Benchmark')][string] $Phase='Capture',
    [ValidateSet('bistro','minecraft')][string] $Scene='bistro',
    [string] $Receipt='tmp/temporal-only-runs.json'
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$hash=(Get-FileHash -LiteralPath $exe).Hash
$records=@()
if(Test-Path -LiteralPath $Receipt){$records=@(Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json)}
if(@($records | Where-Object {$_.scene -eq $Scene -and $_.phase -eq $Phase}).Count){throw 'Already completed: select a new receipt for a separate run'}
$started=[DateTime]::UtcNow.ToString('o')
$arguments=@("-smaaTemporalOnly$Phase",$Scene)
$output=& (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $arguments -Hidden -TimeoutSeconds 1200
$pass=$output | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
if(!$pass){throw 'No completed result'}
$report=($pass -split 'report=',2)[1].Trim()
if((Get-Content -LiteralPath $report -Raw) -notmatch 'Aggregate: PASS'){throw 'Aggregate PASS missing'}
if((Get-FileHash -LiteralPath $exe).Hash -ne $hash){throw 'Executable changed'}
$records += [pscustomobject]@{scene=$Scene;phase=$Phase;window='hidden';source_baseline='e14f122';research_branch='experiment/temporal-only-control';arguments=$arguments;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');executable_sha256=$hash;report=$report;report_sha256=(Get-FileHash -LiteralPath $report).Hash}
ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $Receipt -Encoding utf8
Write-Output $pass
