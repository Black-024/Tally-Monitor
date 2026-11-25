@echo off
chcp 65001 >nul
echo Verificacion contra Tally REAL (te pide tu API Key de forma oculta; no se muestra ni se guarda).
py "%~dp0verify_sync_windows.py"
echo.
pause
