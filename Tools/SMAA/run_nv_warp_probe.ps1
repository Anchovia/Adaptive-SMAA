param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location -LiteralPath $root
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count) { throw 'CMAA2 must be stopped before the independent GPU probe' }
New-Item -ItemType Directory -Force tmp | Out-Null
$fxc='C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe'
& $fxc /nologo /T vs_5_0 /E VS /O3 /Fo tmp/nvprobe-vs.dxbc Tools/SMAA/probe_nv_warp.hlsl
if($LASTEXITCODE) { throw 'VS compilation failed' }
& $fxc /nologo /T ps_5_0 /E PS /O3 /Fo tmp/nvprobe-ps.dxbc Tools/SMAA/probe_nv_warp.hlsl
if($LASTEXITCODE) { throw 'PS compilation failed' }
@'
@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cl /nologo /EHsc /O2 /std:c++17 Tools\SMAA\probe_nv_warp.cpp /Fo:tmp\probe_nv_warp.obj /Fe:tmp\probe_nv_warp.exe /link d3d11.lib d3dcompiler.lib External\NVAPI\amd64\nvapi64.lib
'@ | Set-Content tmp/build_nv_warp_probe.cmd
cmd /c tmp\build_nv_warp_probe.cmd
if($LASTEXITCODE) { throw 'Probe compilation failed' }
$stdout=Join-Path $root 'tmp/nv-warp-probe-result.txt'
$stderr=Join-Path $root 'tmp/nv-warp-probe-error.txt'
$owned=Start-Process -FilePath (Join-Path $root 'tmp/probe_nv_warp.exe') -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
if(!$owned.WaitForExit(60000)) { $owned.Kill();$owned.WaitForExit();throw 'Owned probe timed out; partial result excluded' }
$owned.Refresh()
if($owned.ExitCode -ne 0) { throw "Probe failed: $($owned.ExitCode)" }
Get-Content -LiteralPath $stdout
