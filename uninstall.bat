@echo off
REM Remove the .venv created by install.bat.
REM Leaves source, config.yaml, refs, data, and cache in place.
setlocal
cd /d "%~dp0"

echo === VoiceAnalyzer Uninstall ===

if not exist ".venv\" goto :absent

for %%I in (".venv") do set "ATTR=%%~aI"
echo %ATTR% | find "l" >nul
if not errorlevel 1 goto :link

echo Removing .venv. This can take a while.
rmdir /s /q ".venv"
if exist ".venv\" goto :fail

echo.
echo === Uninstall complete ===
echo Removed .venv.
echo Source, config.yaml, refs, data, and cache were left in place.
goto :eof

:absent
echo .venv is not present. Nothing to remove.
goto :eof

:link
echo .venv is a link. Refusing to remove it.
exit /b 1

:fail
echo Failed to remove .venv. Stop the server if it is using this environment, then run this script again.
exit /b 1
