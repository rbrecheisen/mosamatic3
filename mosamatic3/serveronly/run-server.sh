#!/bin/zsh

set -e

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate mosamatic3

PROJECT_ROOT="$HOME/Documents/Development/GitHub/mosamatic3"
SERVER_DIR="$PROJECT_ROOT/mosamatic3/serveronly"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

cd "$SERVER_DIR"

./run-dockerbackendservices.sh

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py ensure_admin

cat > /tmp/start-mosamatic-celery.sh <<EOF
#!/bin/zsh
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate mosamatic3
cd "$SERVER_DIR"
export PYTHONPATH="$PROJECT_ROOT:\$PYTHONPATH"
python -m celery -A config.celery_app worker --loglevel=info --pool=solo
EOF

chmod +x /tmp/start-mosamatic-celery.sh

osascript <<EOF
tell application "Terminal"
    do script "/tmp/start-mosamatic-celery.sh"
end tell
EOF

python manage.py runserver