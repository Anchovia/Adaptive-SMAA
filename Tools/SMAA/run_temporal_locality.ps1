param(
    [ValidateSet('Capture','Smoke','Benchmark')][string] $Phase = 'Smoke',
    [ValidateSet('bistro','minecraft')][string] $Scene = 'bistro',
    [string] $Receipt = 'tmp/temporal-locality-runs.json'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$exe = Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$beforeHash = (Get-FileHash -LiteralPath $exe).Hash
$argsForDemo = @("-smaaTemporalLocality$Phase",$Scene)
$timeout = if($Phase -eq 'Smoke') {120} else {1800}
$runOutput = & (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $argsForDemo -Hidden -TimeoutSeconds $timeout
$passLine = $runOutput | Where-Object { $_ -match 'PASS:.*report=' } | Select-Object -Last 1
if (!$passLine) { throw 'No completed report was returned' }
if ((Get-FileHash -LiteralPath $exe).Hash -ne $beforeHash) { throw 'Executable changed during run' }
$records = @()
if (Test-Path -LiteralPath $Receipt) { $records = @(Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json) }
$records += [pscustomobject]@{
    scene=$Scene; phase=$Phase; window='hidden'; executable_sha256=$beforeHash
    arguments=$argsForDemo; report=($passLine -split 'report=',2)[1].Trim()
}
New-Item -ItemType Directory -Path (Split-Path -Parent ([IO.Path]::GetFullPath($Receipt))) -Force | Out-Null
ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $Receipt
Write-Output $passLine

