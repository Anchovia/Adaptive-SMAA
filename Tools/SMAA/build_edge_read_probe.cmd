@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %ERRORLEVEL%
pushd "%~dp0..\.."
if not exist "tmp\edge-read-probe" mkdir "tmp\edge-read-probe"
cl /nologo /EHsc /W4 /Fo:"tmp\edge-read-probe\probe.obj" /Fe:"tmp\edge-read-probe\probe.exe" Tools\SMAA\edge_read_raster_probe.cpp d3d11.lib d3dcompiler.lib
set "EDGE_PROBE_BUILD_EXIT=%ERRORLEVEL%"
popd
exit /b %EDGE_PROBE_BUILD_EXIT%
