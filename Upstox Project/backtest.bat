@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python backtest.py %*
if exist "data\backtest\report.html" start "" "data\backtest\report.html"
pause
