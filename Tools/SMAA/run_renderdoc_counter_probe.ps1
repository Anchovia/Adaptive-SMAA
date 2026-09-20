param([ValidateSet('bistro','minecraft')][string] $Scene = '', [switch] $InspectInputs)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$out = Join-Path $root 'tmp/rd-profiler'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$rd = (Get-Item -LiteralPath 'C:/Program Files/RenderDoc/qrenderdoc.exe').FullName
trap {
    @{error=$_.Exception.Message; completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $out 'supervisor-error.json') -Encoding UTF8
    exit 1
}
if (![Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this bounded profiler from an administrator process' }
if (@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count) { throw 'CMAA2 already running' }
$runtime = 'C:/Program Files/NVIDIA Corporation/Nsight Systems 2026.3.1/target-windows-x64/nvperf_grfx_host.dll'
$plugin = Join-Path $out 'plugins/nv/nvperf_grfx_host.dll'
New-Item -ItemType Directory -Path (Split-Path $plugin) -Force | Out-Null
if (!(Test-Path -LiteralPath $plugin)) { Copy-Item -LiteralPath $runtime -Destination $plugin }
if ((Get-FileHash -LiteralPath $runtime).Hash -ne (Get-FileHash -LiteralPath $plugin).Hash) { throw 'Local profiling runtime differs from installed runtime' }
$script = Join-Path $PSScriptRoot 'probe_renderdoc_counters.py'
if ($Scene) {
    @{scene=$Scene} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $out 'job.json') -Encoding UTF8
    $script = Join-Path $PSScriptRoot 'profile_temporal_renderdoc.py'
}
if ($InspectInputs) {
    if ($Scene) { throw 'Choose either scene capture or existing-input inspection' }
    $script = Join-Path $PSScriptRoot 'inspect_temporal_replay_inputs.py'
}
$start = Get-Date
$hostProcess = Start-Process -FilePath $rd -WindowStyle Hidden -WorkingDirectory $out -ArgumentList @('--python',('"'+$script+'"')) -PassThru -RedirectStandardOutput (Join-Path $out 'host-stdout.txt') -RedirectStandardError (Join-Path $out 'host-stderr.txt')
$null = $hostProcess.Handle
$owned = @{}
do {
    foreach ($child in @(Get-CimInstance Win32_Process -Filter "Name='CMAA2.exe'")) {
        if ($child.ParentProcessId -eq $hostProcess.Id -and $child.ExecutablePath -eq (Join-Path $root 'Projects/CMAA2/CMAA2.exe')) {
            $owned[$child.ProcessId] = $child.CreationDate
        }
    }
    $finished = $hostProcess.WaitForExit(500)
} while (!$finished -and ((Get-Date)-$start).TotalSeconds -lt 300)
if (!$finished) { Stop-Process -Id $hostProcess.Id -Force; $hostProcess.WaitForExit() }
$terminatedTarget = $false
foreach ($childId in $owned.Keys) {
    $child = Get-Process -Id $childId -ErrorAction SilentlyContinue
    if ($child -and $child.StartTime -eq $owned[$childId]) {
        if (!$child.WaitForExit(15000)) { Stop-Process -Id $childId -Force; $child.WaitForExit(); $terminatedTarget=$true }
    }
}
$state = [ordered]@{
    timed_out=!$finished; host_exit_code=$hostProcess.ExitCode; target_terminated=$terminatedTarget
    remaining_cmaa2=@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count
    started_utc=$start.ToUniversalTime().ToString('o'); completed_utc=[DateTime]::UtcNow.ToString('o')
    profiler_script_sha256=(Get-FileHash -LiteralPath $script).Hash
    runtime_sha256=(Get-FileHash -LiteralPath $runtime).Hash
}
$statePath = if ($InspectInputs) { Join-Path $out 'run-inputs.json' } elseif ($Scene) { Join-Path $out ("run-$Scene.json") } else { Join-Path $out 'run-capability.json' }
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
if (!$finished -or $terminatedTarget -or $state.remaining_cmaa2) { exit 1 }
$resultPath = if ($InspectInputs) { Join-Path $out 'inputs.json' } elseif ($Scene) { Join-Path $out "$Scene/results.json" } else { Join-Path $out 'counter-probe.json' }
$result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
if ($result.status -notin @('PASS','CAPABILITY_QUERIED')) { throw 'RenderDoc script reported a failure' }
