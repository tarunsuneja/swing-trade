@echo off
cd /d %~dp0
start "SwingScanner" /min py -X utf8 scan_web.py
echo Swing scanner launching - browser will open automatically.
echo Server keeps running in the minimized window (close it to stop).
timeout /t 3 >nul
