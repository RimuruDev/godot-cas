@echo off
rem Double-click this in Explorer to update the CAS fork.
rem All the real work lives in tools\cas.py — this only locates Python and keeps
rem the console window open long enough to read the result.
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem Python prints the progress markers as UTF-8; without this cmd.exe mangles them.
set "PYTHONIOENCODING=utf-8"

set "PY="
where py >nul 2>nul
if !ERRORLEVEL! equ 0 set "PY=py -3"
if not defined PY (
    where python >nul 2>nul
    if !ERRORLEVEL! equ 0 set "PY=python"
)
if not defined PY (
    echo Python 3 was not found on PATH.
    echo Install it from https://www.python.org/downloads/ and tick
    echo "Add python.exe to PATH" in the installer, then re-run this file.
    echo.
    pause
    exit /b 1
)

%PY% "tools\cas.py" update %*
set "STATUS=!ERRORLEVEL!"

echo.
pause
exit /b !STATUS!
