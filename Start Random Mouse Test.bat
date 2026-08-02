@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [AI Mouse Test] Virtuele omgeving ontbreekt.
    echo Start eerst een keer: Start AI Mouse Lab.bat
    echo.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :error

python random_mouse_test.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo [AI Mouse Test] Starten is mislukt.
echo Controleer of je eerst Build Profile hebt uitgevoerd.
echo.
pause
exit /b 1
