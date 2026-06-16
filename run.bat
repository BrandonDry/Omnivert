@echo off
REM Launch Omnivert using the project's virtual environment.
setlocal
cd /d "%~dp0"
if not exist "..\.venv\Scripts\python.exe" (
  echo Could not find the project venv at ..\.venv
  echo Make sure Omnivert lives inside the Omnivert workspace.
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo [note] Frontend not built yet - run build.bat first for the full UI.
)
set PYTHONPATH=%CD%\src
"..\.venv\Scripts\python.exe" -m omnivert
