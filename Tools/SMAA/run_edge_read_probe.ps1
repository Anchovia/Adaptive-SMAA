param([string] $Output = 'tmp/edge-read-probe/output.json')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count) { throw 'CMAA2 must be stopped' }
if (@(Get-Process probe -ErrorAction SilentlyContinue).Count) { throw 'Another probe is running' }
$destination = [IO.Path]::GetFullPath($Output)
New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
$process = Start-Process -FilePath (Join-Path $root 'tmp/edge-read-probe/probe.exe') -ArgumentList 'Tools/SMAA/edge_read_raster_probe.hlsl' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $destination -RedirectStandardError ($destination + '.stderr')
if (!$process.WaitForExit(60000)) {
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit()
    throw 'Edge raster probe timed out; partial result is invalid'
}
if ($process.ExitCode -ne 0) { throw "Edge raster probe failed: $($process.ExitCode)" }
$result = Get-Content -LiteralPath $destination -Raw | ConvertFrom-Json
if ($result.validation -ne 'PASS' -or @($result.fixtures).Count -ne 20) { throw 'Incomplete GPU validation' }
Write-Output "PASS: 20 raster fixtures, $($result.total_pixels) pixels; report=$destination"
