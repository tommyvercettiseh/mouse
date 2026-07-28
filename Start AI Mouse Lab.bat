@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [AI Mouse Lab] Virtuele omgeving maken...
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

echo [AI Mouse Lab] Dependencies controleren...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :error

echo [AI Mouse Lab] Starten...
start "AI Mouse Lab" ".venv\Scripts\pythonw.exe" app.py
exit /b 0

:error
echo.
echo Starten is mislukt. Controleer of Python 3 is geinstalleerd.
pause
exit /b 1
