param(
    [ValidateSet('Capture','Smoke','Benchmark')][string] $Phase = 'Capture',
    [ValidateSet('bistro','minecraft')][string] $Scene = 'bistro',
    [string] $Receipt = 'tmp/temporal-blend-read-runs.json'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$exe = Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$beforeHash = (Get-FileHash -LiteralPath $exe).Hash
$records = @()
if (Test-Path -LiteralPath $Receipt) { $records = @(Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json) }
if (@($records | Where-Object { $_.phase -eq $Phase -and $_.scene -eq $Scene }).Count) { throw 'Duplicate completed scene/phase; use a separate receipt' }
$argsForDemo = @("-smaaTemporalBlendRead$Phase",$Scene)
$started = [DateTime]::UtcNow.ToString('o')
$runOutput = & (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $argsForDemo -Hidden -TimeoutSeconds 1200
$passLine = $runOutput | Where-Object { $_ -match 'PASS:.*report=' } | Select-Object -Last 1
if (!$passLine) { throw 'No completed report was returned' }
if ((Get-FileHash -LiteralPath $exe).Hash -ne $beforeHash) { throw 'Executable changed during run' }
$report = ($passLine -split 'report=',2)[1].Trim()
$records += [pscustomobject]@{
    scene=$Scene; phase=$Phase; window='hidden'; executable_sha256=$beforeHash
    started_utc=$started; completed_utc=[DateTime]::UtcNow.ToString('o')
    arguments=$argsForDemo; report=$report; report_sha256=(Get-FileHash -LiteralPath $report).Hash
}
New-Item -ItemType Directory -Path (Split-Path -Parent ([IO.Path]::GetFullPath($Receipt))) -Force | Out-Null
ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $Receipt -Encoding utf8
Write-Output $passLine
