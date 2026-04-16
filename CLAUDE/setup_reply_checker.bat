@echo off
setlocal

:: ── Paths ──────────────────────────────────────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%..\.venv\Scripts\python.exe"
set "REPLY_SCRIPT=%SCRIPT_DIR%reply_checker.py"
set "TASK_NAME=MedicineReplyChecker"

:: ── Pick Python ────────────────────────────────────────────────────────────
if exist "%VENV_PYTHON%" (
    set "PYTHON=%VENV_PYTHON%"
) else (
    set "PYTHON=python"
)

:: ── Register Task (every 30 minutes) ──────────────────────────────────────
echo.
echo  Medicine Reply Checker -- Task Scheduler Setup
echo  ================================================
echo  Task name : %TASK_NAME%
echo  Runs every: 30 minutes
echo  Python    : %PYTHON%
echo  Script    : %REPLY_SCRIPT%
echo.

schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%PYTHON%\" \"%REPLY_SCRIPT%\"" ^
    /sc MINUTE ^
    /mo 30 ^
    /f

if %ERRORLEVEL% == 0 (
    echo.
    echo  [OK] Reply checker scheduled every 30 minutes.
    echo       When you reply to the morning email, your dose will be
    echo       marked within 30 minutes and a confirmation sent back.
    echo.
    echo  Useful commands:
    echo    Run now  : schtasks /run /tn "%TASK_NAME%"
    echo    Check    : schtasks /query /tn "%TASK_NAME%"
    echo    Remove   : schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo  [ERROR] Failed to create task.
    echo  Try right-clicking this .bat file and selecting "Run as administrator".
)

echo.
pause
