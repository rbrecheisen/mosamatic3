@echo off
cd /d "%~dp0"
echo DICOM Series Indexer - DuckDB
echo Open http://localhost:8765 in Chrome or Edge.
echo Keep this window open while using the tool. Close it when finished.
start "" "http://localhost:8765"
py -3 -m http.server 8765 --bind 127.0.0.1
if errorlevel 1 (
  echo Python launcher unavailable. Trying python...
  python -m http.server 8765 --bind 127.0.0.1
)
pause
