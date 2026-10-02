@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
python autopilot\make_dashboard.py
start "" "%~dp0..\dashboard.html"
