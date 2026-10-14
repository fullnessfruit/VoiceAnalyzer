@echo off
setlocal
set "OCR_BROKER_URL=http://127.0.0.1:3100"
call "%~dp0server.bat"
exit /b %errorlevel%
