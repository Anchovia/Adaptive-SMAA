param(
    [ValidateSet('Smoke','Benchmark')][string] $Phase = 'Smoke',
    [ValidateSet('bistro','minecraft')][string] $Scene = 'bistro',
    [Parameter(Mandatory)][ValidateSet('AB','BA')][string] $Order,
    [ValidateRange(0,5)][int] $PairIndex = 0,
    [string] $Receipt = 'tmp/temporal-pair-runs.json'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$exe = Join-Path $root 'Projects/CMAA2/CMAA2.exe'
$beforeHash = (Get-FileHash -LiteralPath $exe).Hash
$records = @()
if (Test-Path -LiteralPath $Receipt) { $records = @(Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json) }
if (@($records | Where-Object { $_.phase -eq $Phase -and $_.scene -eq $Scene -and $_.pair_index -eq $PairIndex }).Count) {
    throw 'Duplicate scene/phase/pair index; preserve this run separately instead of overwriting'
}
$argsForDemo = @("-smaaTemporalPair$Phase",$Scene,$Order)
$timeout = if($Phase -eq 'Smoke') {180} else {600}
$started = [DateTime]::UtcNow.ToString('o')
$runOutput = & (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -CMAA2Arguments $argsForDemo -Hidden -TimeoutSeconds $timeout
$passLine = $runOutput | Where-Object { $_ -match 'PASS:.*report=' } | Select-Object -Last 1
if (!$passLine) { throw 'No completed report was returned' }
if ((Get-FileHash -LiteralPath $exe).Hash -ne $beforeHash) { throw 'Executable changed during run' }
$report = ($passLine -split 'report=',2)[1].Trim()
$content = Get-Content -LiteralPath $report -Raw
if (!$content.Contains("Independent process pair order: $Order") -or !$content.Contains('Common preconditioning: O-T2X-R')) {
    throw 'Pair order or common preconditioning report mismatch'
}
$records += [pscustomobject]@{
    scene=$Scene; phase=$Phase; order=$Order; pair_index=$PairIndex; window='hidden'
    started_utc=$started; completed_utc=[DateTime]::UtcNow.ToString('o')
    executable_sha256=$beforeHash; arguments=$argsForDemo; report=$report
    report_sha256=(Get-FileHash -LiteralPath $report).Hash
}
New-Item -ItemType Directory -Path (Split-Path -Parent ([IO.Path]::GetFullPath($Receipt))) -Force | Out-Null
ConvertTo-Json -InputObject @($records) -Depth 5 | Set-Content -LiteralPath $Receipt -Encoding utf8
Write-Output $passLine
