@echo off
REM Start the voice broker worker and shut Windows down after a fixed time.
REM The timer remains active if this window closes. Cancel with: shutdown /a
setlocal
set "SHUTDOWN_AFTER_SEC=7200"
shutdown /s /t %SHUTDOWN_AFTER_SEC% /c "VoiceAnalyzer worker: timed shutdown (%SHUTDOWN_AFTER_SEC% s). Cancel with: shutdown /a"
if errorlevel 1 (
  echo Refusing to start - could not schedule the shutdown. A shutdown may already be pending; run "shutdown /a" and start again.
  exit /b 1
)
echo Shutdown scheduled - seconds: %SHUTDOWN_AFTER_SEC% (cancel: shutdown /a)
call "%~dp0server.bat"
exit /b %errorlevel%
