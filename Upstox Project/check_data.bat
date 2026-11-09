@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python check_data.py
pause
