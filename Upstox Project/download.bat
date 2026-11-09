@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python data_download.py %*
pause
