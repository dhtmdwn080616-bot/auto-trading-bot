@echo off
rem Emergency stop: Jubis skips every cycle while the STOP file exists.
echo stopped by user> "%~dp0STOP"
echo Jubis stopped. Run resume.bat to start again.
pause
