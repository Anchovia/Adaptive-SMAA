@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %ERRORLEVEL%
pushd "%~dp0..\.."
if not exist "tmp\dejitter-probe" mkdir "tmp\dejitter-probe"
cl /nologo /EHsc /W4 /Fo:"tmp\dejitter-probe\probe.obj" /Fe:"tmp\dejitter-probe\probe.exe" Tools\SMAA\dejitter_sampling_probe.cpp d3d11.lib d3dcompiler.lib
set "DEJITTER_BUILD_EXIT=%ERRORLEVEL%"
popd
exit /b %DEJITTER_BUILD_EXIT%
