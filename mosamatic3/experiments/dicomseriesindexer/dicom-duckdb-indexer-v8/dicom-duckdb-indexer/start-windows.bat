@echo off
cd /d "%~dp0"
echo DICOM Series Indexer - DuckDB v1.3.3
echo Serving from: %CD%
echo Open http://localhost:8765 in Chrome or Edge.
echo Keep this window open while using the tool. Close it when finished.
echo.
where py >nul 2>nul
if %errorlevel%==0 goto run_py
where python >nul 2>nul
if %errorlevel%==0 goto run_python
echo ERROR: Python 3 was not found. Install Python or start a local static file server.
goto end
:run_py
py -3 -m http.server 8765 --bind 127.0.0.1
goto server_exit
:run_python
python -m http.server 8765 --bind 127.0.0.1
:server_exit
echo.
echo The server has stopped. If port 8765 was busy, close the older server first.
:end
pause
