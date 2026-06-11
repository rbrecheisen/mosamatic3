#!/bin/zsh

set -e

# Activate conda
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate mosamatic3

# Project paths
PROJECT_ROOT="$HOME/Documents/Development/GitHub/mosamatic3"
SERVER_DIR="$PROJECT_ROOT/mosamatic3/serveronly"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

cd "$SERVER_DIR"

# Start Redis only, not the Docker worker
./run-dockerbackendservices.sh

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py ensure_admin

# Start Celery in a separate macOS Terminal window
osascript <<EOF
tell application "Terminal"
    do script "source \\\"\$(conda info --base)/etc/profile.d/conda.sh\\\"; conda activate mosamatic3; cd \\\"$SERVER_DIR\\\"; export PYTHONPATH=\\\"$PROJECT_ROOT:\\\$PYTHONPATH\\\"; python -m celery -A config.celery_app worker --loglevel=info --pool=solo"
end tell
EOF

# Start Django in this terminal
python manage.py runserver