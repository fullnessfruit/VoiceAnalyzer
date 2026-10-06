@echo off
REM Delete only the shared key. Python can be system-installed after .venv is removed.
setlocal
echo This key is shared by ImageAnalyzer, VoiceAnalyzer, and the OCR broker.
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0app\shared_secret.py" delete
) else (
  where py >nul 2>&1
  if errorlevel 1 (
    python "%~dp0app\shared_secret.py" delete
  ) else (
    py -3 "%~dp0app\shared_secret.py" delete
  )
)
if errorlevel 1 exit /b 1
echo Key deletion complete. Existing clients need the same replacement key.
pause
