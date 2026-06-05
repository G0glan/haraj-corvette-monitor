@echo off
echo Installing dependencies...
pip install requests >nul 2>&1

echo Starting Haraj Corvette Monitor...
echo Leave this window open. Press Ctrl+C to stop.
echo.

:loop
python haraj_monitor.py
echo.
echo Waiting 10 minutes before next check...
timeout /t 600 /nobreak >nul
goto loop
