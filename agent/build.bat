@echo off
:: ============================================================
:: build.bat — Build rdm-agent on Windows
:: Requires: Visual Studio 2022 (cl.exe), CMake 3.20+, vcpkg
:: ============================================================
setlocal EnableDelayedExpansion

set BUILD_TYPE=%1
if "%BUILD_TYPE%"=="" set BUILD_TYPE=Release

:: ── Locate vcpkg ────────────────────────────────────────────
if not defined VCPKG_ROOT (
    if exist "C:\vcpkg\vcpkg.exe" (
        set VCPKG_ROOT=C:\vcpkg
    ) else if exist "%USERPROFILE%\vcpkg\vcpkg.exe" (
        set VCPKG_ROOT=%USERPROFILE%\vcpkg
    ) else (
        echo ERROR: vcpkg not found. Set VCPKG_ROOT or install to C:\vcpkg
        echo   git clone https://github.com/microsoft/vcpkg C:\vcpkg
        echo   C:\vcpkg\bootstrap-vcpkg.bat
        exit /b 1
    )
)
echo vcpkg: %VCPKG_ROOT%

:: ── Locate Visual Studio ────────────────────────────────────
set VSWHERE="%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist %VSWHERE% (
    echo ERROR: vswhere.exe not found. Install Visual Studio 2022.
    exit /b 1
)
for /f "usebackq tokens=*" %%i in (`%VSWHERE% -latest -property installationPath`) do set VS_PATH=%%i
call "%VS_PATH%\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1

:: ── stb_image_write.h ───────────────────────────────────────
set STB_PATH=third_party\include\stb_image_write.h
if not exist "%STB_PATH%" (
    echo Downloading stb_image_write.h ...
    mkdir third_party\include 2>nul
    powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/nothings/stb/master/stb_image_write.h' -OutFile '%STB_PATH%'"
    if !ERRORLEVEL! neq 0 (
        echo ERROR: Failed to download stb_image_write.h
        exit /b 1
    )
)

:: ── Configure ───────────────────────────────────────────────
set BUILD_DIR=build\%BUILD_TYPE%
cmake -B "%BUILD_DIR%" -S . ^
    -G "Visual Studio 17 2022" -A x64 ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_TOOLCHAIN_FILE="%VCPKG_ROOT%\scripts\buildsystems\vcpkg.cmake" ^
    -DVCPKG_TARGET_TRIPLET=x64-windows-static
if !ERRORLEVEL! neq 0 ( echo CMake configure failed & exit /b 1 )

:: ── Build ────────────────────────────────────────────────────
cmake --build "%BUILD_DIR%" --config %BUILD_TYPE% --parallel
if !ERRORLEVEL! neq 0 ( echo Build failed & exit /b 1 )

echo.
echo Build succeeded: %BUILD_DIR%\%BUILD_TYPE%\rdm-agent.exe
endlocal
