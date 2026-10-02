@echo off
rem Jubis: register a Windows scheduled task that runs one cycle every 2 hours.
chcp 65001 >nul
cd /d "%~dp0.."
if not exist ".git" (
  where git >nul 2>nul && git init -q && git add -A && git commit -q -m "jubis start"
)
schtasks /create /tn "Jubis" /sc hourly /mo 2 /tr "\"%~dp0run_once.bat\"" /f
echo.
echo Done. Jubis will wake up every 2 hours.
echo  - Stop:    stop.bat
echo  - Resume:  resume.bat
echo  - Remove:  uninstall_task.bat
pause
