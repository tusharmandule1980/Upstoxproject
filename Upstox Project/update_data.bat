@echo off
rem Brings the backtest data up to date (read only - no orders). Run after 15:35 with a valid login (run.bat).
rem 1. expired contracts in full  2. contracts not expired yet (incl. today after 15:35)  3. 3/5/15-min files
rem 4. the 5000/backtest report   5. Rally data and S1-S3 statistics
cd /d "%~dp0"
set PY="%~dp0.venv\Scripts\python.exe"
echo === 1/5 Expired contracts ===
%PY% data_download.py || goto :fail
echo === 2/5 Contracts not expired yet ===
%PY% download_live.py || goto :fail
echo === 3/5 3, 5 and 15-minute files ===
%PY% resample_data.py || goto :fail
echo === 4/5 Backtest report (takes 10-20 min) ===
%PY% backtest.py || goto :fail
echo === 5/5 Rally data and statistics ===
cd /d "C:\Users\tusha\Downloads\Rally"
%PY% nifty_behaviour.py > output\nifty_behaviour.txt || goto :fail
%PY% opt_cache.py || goto :fail
%PY% build_all_strategies_stats.py || goto :fail
%PY% make_backtest_summary.py || goto :fail
echo.
echo All done. Open http://127.0.0.1:5000/backtest and Rally_All_Strategies_Statistics.xlsx
pause
exit /b 0
:fail
echo.
echo Stopped: the step above failed (log in again with run.bat if it says the token expired).
pause
exit /b 1
