@echo off
rem Jubis: run one autonomous cycle. Called by Task Scheduler (install_task.bat).
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
set PY=python
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
%PY% autopilot\jubis_cycle.py
