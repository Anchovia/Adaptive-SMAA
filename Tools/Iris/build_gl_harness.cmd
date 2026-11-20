@echo off
rem Builds iris_gl_harness.exe with the Visual Studio 2022 x64 toolchain into the folder given as %1.
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cl /nologo /O2 /EHsc /std:c++17 /Fe:"%~1\iris_gl_harness.exe" /Fo:"%~1\\" "%~dp0iris_gl_harness.cpp" opengl32.lib user32.lib gdi32.lib
