@echo off
REM Pull voice jobs from the same broker as ImageAnalyzer; no local server port.
cd /d "%~dp0"
if errorlevel 1 exit /b 1
if "%OCR_BROKER_URL%"=="" set "OCR_BROKER_URL=http://ec2-35-78-169-107.ap-northeast-1.compute.amazonaws.com:3100"
REM Set to 0 to disable. Only discharging batteries trigger shutdown (120s grace).
if "%VOICE_WORKER_BATTERY_SHUTDOWN_PERCENT%"=="" set "VOICE_WORKER_BATTERY_SHUTDOWN_PERCENT=25"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m app.worker
) else (
  python -m app.worker
)
exit /b %errorlevel%
