param([switch] $Trace)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$nsys='C:/Program Files/NVIDIA Corporation/Nsight Systems 2026.3.1/target-windows-x64/nsys.exe'
$dir=Join-Path $root ('tmp/dx11-profiler-'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $dir | Out-Null
$version=(& $nsys --version | Out-String).Trim()
$support=(& $nsys profile --gpu-metrics-devices=help 2>&1 | Out-String).Trim()
$admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$result=[ordered]@{ version=$version; administrator=$admin; metric_support=$support; hardware_metrics_collected=$false; trace_requested=[bool]$Trace }
if($Trace) {
    if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count) { throw 'Existing CMAA2 process; refusing concurrent trace' }
    $exe=Join-Path $root 'Projects/CMAA2/CMAA2.exe'
    $result.executable_sha256=(Get-FileHash -LiteralPath $exe).Hash
    $argsForProfiler=@('profile','--sample=none','--trace=dx11,dx11-annotations','--gpu-metrics-devices=none',
        '--duration=15','--kill=false','--stop-on-exit=true',('--output="'+(Join-Path $dir 'api-trace')+'"'),
        ('"'+$exe+'"'),'-smaaTemporalDependencySmoke','minecraft','-smaaNonInteractiveShaderCompile')
    $result.arguments=$argsForProfiler
    $start=Get-Date
    $proc=Start-Process -FilePath $nsys -ArgumentList $argsForProfiler -WorkingDirectory (Split-Path $exe) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dir 'stdout.txt') -RedirectStandardError (Join-Path $dir 'stderr.txt')
    # Keep track of only this profiler's direct CMAA2 child for bounded cleanup.
    $owned=@{}
    do {
        foreach($child in @(Get-CimInstance Win32_Process -Filter "Name='CMAA2.exe'")) {
            if($child.ParentProcessId -eq $proc.Id -and $child.ExecutablePath -eq $exe) { $owned[$child.ProcessId]=$child.CreationDate }
        }
        $finished=$proc.WaitForExit(500)
    } while(!$finished -and ((Get-Date)-$start).TotalSeconds -lt 90)
    if(!$finished) { Stop-Process -Id $proc.Id -Force; $proc.WaitForExit() }
    $result.profiler_exit_code=$proc.ExitCode
    $result.timed_out=!$finished
    foreach($id in $owned.Keys) {
        $child=Get-Process -Id $id -ErrorAction SilentlyContinue
        if($child -and $child.Path -eq $exe -and $child.StartTime -eq $owned[$id]) {
            if(!$child.WaitForExit(30000)) { Stop-Process -Id $id -Force; $result.timed_out=$true }
        }
    }
    $result.remaining_cmaa2=@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count
    $result.reports=@(Get-ChildItem -LiteralPath $dir -Filter '*.nsys-rep' | Select-Object -ExpandProperty Name)
    $result.stdout=Get-Content -LiteralPath (Join-Path $dir 'stdout.txt') -Raw
    $result.stderr=Get-Content -LiteralPath (Join-Path $dir 'stderr.txt') -Raw
    if((Get-FileHash -LiteralPath $exe).Hash -ne $result.executable_sha256) { throw 'Executable changed' }
}
$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $dir 'probe.json')
Write-Output (Join-Path $dir 'probe.json')
if($Trace -and ($result.remaining_cmaa2 -ne 0 -or $result.timed_out)) { throw 'Trace did not terminate cleanly; results are diagnostic only' }
