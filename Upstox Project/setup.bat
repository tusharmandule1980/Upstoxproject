@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Python not found. Install Python 3.11+ from python.org and tick "Add to PATH". & pause & exit /b 1)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m pytest -q
echo.
echo Setup complete. Run run.bat to start the app.
pause
