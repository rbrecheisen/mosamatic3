#!/bin/sh
cd "$(dirname "$0")" || exit 1
echo 'Open http://localhost:8765 in Chrome or Edge. Keep this terminal running.'
python3 -m http.server 8765 --bind 127.0.0.1
