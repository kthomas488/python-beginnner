@echo off
setlocal

:: ── Paths ──────────────────────────────────────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\venv\Scripts\python.exe"
set "VENV_PYTHON_DOT=%SCRIPT_DIR%..\.venv\Scripts\python.exe"
set "ALERT_SCRIPT=%SCRIPT_DIR%daily_alert.py"
set "TASK_NAME=MedicineDailyAlert"
set "ALERT_TIME=08:00"

:: ── Pick Python ────────────────────────────────────────────────────────────
if exist "%VENV_PYTHON_DOT%" (
    set "PYTHON=%VENV_PYTHON_DOT%"
) else if exist "%VENV_PYTHON%" (
    set "PYTHON=%VENV_PYTHON%"
) else (
    set "PYTHON=python"
)

:: ── Register Task ──────────────────────────────────────────────────────────
echo.
echo  Medicine Daily Alert -- Task Scheduler Setup
echo  =============================================
echo  Task name : %TASK_NAME%
echo  Run time  : %ALERT_TIME% every day
echo  Python    : %PYTHON%
echo  Script    : %ALERT_SCRIPT%
echo.

schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%PYTHON%\" \"%ALERT_SCRIPT%\"" ^
    /sc DAILY ^
    /st %ALERT_TIME% ^
    /f

if %ERRORLEVEL% == 0 (
    echo.
    echo  [OK] Task scheduled! You will get a daily medicine email at %ALERT_TIME%.
    echo.
    echo  Useful commands:
    echo    Run now   : schtasks /run /tn "%TASK_NAME%"
    echo    Check     : schtasks /query /tn "%TASK_NAME%"
    echo    Remove    : schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo  [ERROR] Failed to create task.
    echo  Try right-clicking this .bat file and selecting "Run as administrator".
)

echo.
pause
