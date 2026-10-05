@echo off
REM Start VoiceAnalyzer on 127.0.0.1:8000.
REM Uses .venv when it exists. Override with HOST and PORT.
cd /d "%~dp0"

if "%HOST%"=="" set HOST=127.0.0.1
if "%PORT%"=="" set PORT=8000

if exist ".venv\Scripts\python.exe" goto :venv
python -m uvicorn app.main:app --host %HOST% --port %PORT%
goto :eof

:venv
".venv\Scripts\python.exe" -m uvicorn app.main:app --host %HOST% --port %PORT%
