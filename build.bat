@echo off
REM Install frontend dependencies and build the production UI into frontend\dist.
setlocal
cd /d "%~dp0"
echo === Installing frontend dependencies ===
call npm install --prefix frontend
if errorlevel 1 (
  echo npm install failed.
  pause
  exit /b 1
)
echo === Building production UI ===
call npm run build --prefix frontend
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
echo === Copying UI into Python package ===
if exist "src\omnivert\web" rmdir /s /q "src\omnivert\web"
xcopy "frontend\dist" "src\omnivert\web" /E /I /Y >nul
if errorlevel 1 (
  echo Could not copy frontend dist into package web assets.
  pause
  exit /b 1
)
echo === Done. Launch the app with run.bat ===
