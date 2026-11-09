@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python resample_data.py %*
pause
