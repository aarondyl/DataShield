@echo off
title DataShield Launcher
cd /d "%~dp0"

REM ============ DataShield one-click launcher ============
REM Double-click to start backend (8000) and frontend (5173).
REM Close the two spawned console windows to stop the services.

set PATH=C:\Users\jiang\.local\node;%PATH%

python -c "import fastapi, langgraph" >nul 2>nul
if errorlevel 1 (
    echo First run: installing backend dependencies...
    python -m pip install -r backend\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

if not exist frontend\node_modules (
    echo First run: installing frontend dependencies...
    pushd frontend
    call npm install
    popd
)

echo.
echo Starting backend  at http://localhost:8000 ...
start "DataShield Backend (8000)" cmd /k "cd /d %~dp0backend && uvicorn app.main:app --port 8000"
timeout /t 6 /nobreak >nul

echo Starting frontend at http://localhost:5173 ...
start "DataShield Frontend (5173)" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 8 /nobreak >nul

echo.
echo Done. Opening http://localhost:5173 in your browser.
echo Demo data included: ABC Technology + SmartWatch X1.
echo Close the two DataShield console windows to stop.
start http://localhost:5173
pause
