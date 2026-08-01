@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    echo.
    echo [AI Mouse Lab] Python 3 is niet gevonden.
    echo Installeer Python via https://www.python.org/downloads/windows/
    echo Zet tijdens installatie een vinkje bij: Add python.exe to PATH
    echo Sluit daarna PowerShell en start deze launcher opnieuw.
    echo.
    pause
    exit /b 1
)

set "NEED_INSTALL="
if not exist ".venv\Scripts\python.exe" (
    echo [AI Mouse Lab] Virtuele omgeving maken...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
    set "NEED_INSTALL=1"
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :error

python -c "import customtkinter" >nul 2>nul
if errorlevel 1 set "NEED_INSTALL=1"

if defined NEED_INSTALL (
    echo [AI Mouse Lab] Benodigdheden installeren...
    python -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)

python app.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo [AI Mouse Lab] Starten is mislukt.
echo Bekijk de fout hierboven en logs\ai_mouse_lab.log.
echo.
pause
exit /b 1
