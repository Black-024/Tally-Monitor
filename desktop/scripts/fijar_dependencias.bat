@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fijar_dependencias.ps1"
echo.
pause
