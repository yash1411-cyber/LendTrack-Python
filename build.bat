@echo off
echo ====================================
echo  LendTrack - Build Windows EXE
echo ====================================

:: Install dependencies
pip install customtkinter openpyxl pyinstaller

:: Build single-file executable
:: --windowed      : no console window
:: --onefile       : single .exe
:: --name          : output filename
:: --add-data      : bundle customtkinter assets
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "LendTrack" ^
  --add-data "%LOCALAPPDATA%\Programs\Python\Python311\Lib\site-packages\customtkinter;customtkinter" ^
  --hidden-import customtkinter ^
  --hidden-import openpyxl ^
  --hidden-import sqlite3 ^
  main.py

echo.
echo Build complete! Find LendTrack.exe in the dist\ folder.
pause
