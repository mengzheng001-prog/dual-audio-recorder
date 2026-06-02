@echo off
REM ==== Install Recoder dependencies ====
REM Requires Python on PATH. If behind a proxy, set HTTP_PROXY/HTTPS_PROXY first.
echo Installing dependencies...
python -m pip install -r "%~dp0requirements.txt"
echo.
echo Done. Press any key to exit.
pause >nul
