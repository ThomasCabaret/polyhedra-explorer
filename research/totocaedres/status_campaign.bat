@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\status_campaign.ps1"
exit /b %ERRORLEVEL%
