@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is niet gevonden. Installeer Python en voeg het toe aan PATH.
  pause
  exit /b 1
)

if not exist .venv (
  python -m venv .venv
  if errorlevel 1 goto :error
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python run_fixed.py
if errorlevel 1 goto :error
endlocal
exit /b 0

:error
echo.
echo Starten is mislukt.
pause
endlocal
exit /b 1
