@echo off
REM Portable Windows EXE build. Uses the repo folder and the active Python
REM environment. Does not hardcode a user or site-packages path.
setlocal EnableExtensions
cd /d "%~dp0"

echo ====================================
echo  LendTrack - Build Windows EXE
echo ====================================

set "PYEXE="
set "PYOPT="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYEXE=%~dp0.venv\Scripts\python.exe"
    echo Using .venv Python
) else (
    py -3.11 -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo ERROR: No .venv Python and py -3.11 failed.
        echo Create a venv with Python 3.11 and: pip install -r requirements.txt
        exit /b 1
    )
    set "PYEXE=py"
    set "PYOPT=-3.11"
    echo Using py -3.11
)

"%PYEXE%" %PYOPT% -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo ERROR: customtkinter is not installed in this Python.
    echo Activate .venv and run: pip install -r requirements.txt
    exit /b 1
)

"%PYEXE%" %PYOPT% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller is not installed in this Python.
    echo Activate .venv and run: pip install -r requirements.txt
    echo PyInstaller is listed in requirements.txt for packaging.
    exit /b 1
)

set "CTK_DIR="
for /f "usebackq delims=" %%I in (`"%PYEXE%" %PYOPT% -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"`) do set "CTK_DIR=%%I"
if not defined CTK_DIR (
    echo ERROR: Could not resolve the customtkinter package directory.
    exit /b 1
)
echo customtkinter assets: %CTK_DIR%

"%PYEXE%" %PYOPT% -m PyInstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name "LendTrack" ^
  --add-data "%CTK_DIR%;customtkinter" ^
  --hidden-import customtkinter ^
  --hidden-import openpyxl ^
  --hidden-import pandas ^
  --hidden-import sqlite3 ^
  main.py
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

echo.
echo Build complete. Output: dist\LendTrack.exe
endlocal
exit /b 0
