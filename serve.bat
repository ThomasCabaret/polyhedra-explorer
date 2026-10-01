@echo off
setlocal
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js est requis. Installez la version LTS depuis https://nodejs.org/
  exit /b 1
)
cd /d "%~dp0"
node scripts\serve.mjs %*
