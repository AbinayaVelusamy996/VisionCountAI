@echo off
cd /d "%~dp0"
where node >nul 2>&1 || (echo Node.js not found & pause & exit /b 1)
if not exist node_modules ( npm install )
npm run dev
pause
