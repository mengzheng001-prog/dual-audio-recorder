@echo off
REM ==== Launch Recoder ====
REM Requires Python on PATH and deps installed (see install.bat).
REM If you use a proxy and the first model download fails, set HTTP_PROXY/HTTPS_PROXY.
cd /d "%~dp0"
python "%~dp0app.py"
if errorlevel 1 (
  echo.
  echo App exited with an error. See messages above. Press any key to close.
  pause >nul
)
