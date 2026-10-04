@echo off
REM LendTrack development launcher — repo-relative, no hardcoded user paths.
setlocal
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
) else (
    echo [.venv not found] Falling back to py -3.11
    py -3.11 "%~dp0main.py"
)

endlocal
