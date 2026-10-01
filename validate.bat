@echo off
setlocal
where npm >nul 2>nul
if errorlevel 1 (
  echo npm est requis. Installez la version LTS de Node.js depuis https://nodejs.org/
  exit /b 1
)
cd /d "%~dp0"
call npm run validate
