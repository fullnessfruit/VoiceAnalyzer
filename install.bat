@echo off
REM Create or reuse .venv and install requirements.txt.
REM Does not download model weights. Python 3.10 or 3.11 is preferred.
REM Python 3.12 and newer warns and continues. Below 3.10 stops.
setlocal
cd /d "%~dp0"
set "PYFILE=%TEMP%\voiceanalyzer-python.txt"

echo === VoiceAnalyzer Install ===

git --version >nul 2>&1
if errorlevel 1 goto :no_git

if exist ".venv\Scripts\python.exe" goto :use_existing

call :find_python
if errorlevel 1 goto :no_python

"%PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto :too_old

echo Creating .venv
"%PY%" -m venv .venv
if errorlevel 1 goto :venv_fail
if not exist ".venv\Scripts\python.exe" goto :venv_fail
goto :use_venv

:use_existing
echo Using existing .venv

:use_venv
set "PY=.venv\Scripts\python.exe"

"%PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto :too_old_venv

echo Using Python:
"%PY%" -c "import sys; print(sys.version)"

"%PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 goto :deps
echo WARNING: Python 3.12 or newer is not the intended runtime. Python 3.10 or 3.11 is preferred. Continuing.

:deps
echo Upgrading pip
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :pip_fail
echo Installing requirements.txt. This can take a while.
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :pip_fail

where ffmpeg >nul 2>&1
if errorlevel 1 echo WARNING: ffmpeg is not on PATH. The server cannot read media until ffmpeg is installed.
where ffprobe >nul 2>&1
if errorlevel 1 echo WARNING: ffprobe is not on PATH. Duration checks need ffprobe.

echo.
echo === Install complete ===
echo.
echo Next:
echo   1. Put reference wavs in refs\{speaker_id}\
echo   2. Put the media to search under data\
echo   3. Optional: set HUGGINGFACE_TOKEN for pyannote diarization
echo   4. Start the server with server.bat
echo.
echo Model weights are downloaded on first use. This script does not fetch them.
goto :eof

:find_python
set "PY="
where py >nul 2>&1
if errorlevel 1 goto :find_plain
py -3.11 -c "import sys; print(sys.executable)" > "%PYFILE%" 2>nul
if errorlevel 1 goto :find_310
call :read_python_path
if errorlevel 1 goto :find_310
exit /b 0

:find_310
py -3.10 -c "import sys; print(sys.executable)" > "%PYFILE%" 2>nul
if errorlevel 1 goto :find_plain
call :read_python_path
if errorlevel 1 goto :find_plain
exit /b 0

:find_plain
where python >nul 2>&1
if errorlevel 1 goto :find_fail
python -c "import sys; print(sys.executable)" > "%PYFILE%" 2>nul
if errorlevel 1 goto :find_fail
call :read_python_path
if errorlevel 1 goto :find_fail
exit /b 0

:find_fail
if exist "%PYFILE%" del "%PYFILE%" >nul 2>&1
exit /b 1

:read_python_path
set "PY="
for /f "usebackq delims=" %%I in ("%PYFILE%") do set "PY=%%I"
if exist "%PYFILE%" del "%PYFILE%" >nul 2>&1
if not defined PY exit /b 1
exit /b 0

:no_git
echo git is required. wespeaker is installed from git+https://github.com/wenet-e2e/wespeaker.git
exit /b 1

:no_python
echo Python 3.10 or newer was not found. Install Python 3.11 and run this script again.
exit /b 1

:too_old
echo This Python is older than 3.10. Install Python 3.11 and run this script again.
exit /b 1

:too_old_venv
echo The Python in .venv is older than 3.10. .venv was left in place.
echo Install Python 3.11, remove .venv, and run this script again.
exit /b 1

:venv_fail
echo Failed to create .venv
exit /b 1

:pip_fail
echo pip install failed
exit /b 1
