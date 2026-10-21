@echo off
rem FociQuant launcher for Windows - double-click it in Explorer.
rem First run: creates a private Python environment in .venv and installs FociQuant (a few minutes).
rem Later runs: just starts the app.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto run

set "PY="
where py >nul 2>nul
if errorlevel 1 goto trypython
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
:trypython
if defined PY goto install
where python >nul 2>nul
if errorlevel 1 goto nopython
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY goto nopython

:install
echo First run: creating .venv with %PY% and installing FociQuant (a few minutes)...
%PY% -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -e ".[all]"
if errorlevel 1 goto failclean

:run
".venv\Scripts\python.exe" -m fociquant_gui.app %*
set "RC=%errorlevel%"
if not "%RC%"=="0" pause
exit /b %RC%

:nopython
echo Python 3.10 or newer was not found.
echo Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and double-click this file again.
pause
exit /b 1

:failclean
rmdir /s /q .venv
:fail
echo Installation failed - see the messages above.
pause
exit /b 1
