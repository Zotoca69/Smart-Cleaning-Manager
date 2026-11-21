@echo off
rem POC12C offline Windows test package - synthetic data only, no Home Assistant connection.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_tests.ps1"
echo.
pause
