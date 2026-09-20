param([Parameter(Mandatory)][string] $OutputDirectory)
$ErrorActionPreference = 'Stop'
$nsys = 'C:/Program Files/NVIDIA Corporation/Nsight Systems 2026.3.1/target-windows-x64/nsys.exe'
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$administrator = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
$result = [ordered]@{
    started_utc = [DateTime]::UtcNow.ToString('o')
    administrator = $administrator
    purpose = 'Read-only NVIDIA GPU metrics capability query; no capture or permission-policy change'
    hardware_metrics_collected = $false
}
try {
    $result.version = (& $nsys --version 2>&1 | Out-String).Trim()
    $result.devices = (& $nsys profile --gpu-metrics-devices=help 2>&1 | Out-String).Trim()
    $result.devices_exit_code = $LASTEXITCODE
    $result.metric_sets = (& $nsys profile --gpu-metrics-devices=all --gpu-metrics-set=help 2>&1 | Out-String).Trim()
    $result.metric_sets_exit_code = $LASTEXITCODE
    $result.completed_utc = [DateTime]::UtcNow.ToString('o')
} catch {
    $result.error = $_.Exception.Message
} finally {
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'access.json') -Encoding UTF8
}
if ($result.error) { exit 1 }
