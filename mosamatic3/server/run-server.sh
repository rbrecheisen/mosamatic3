#!/bin/zsh

set -e

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate mosamatic3

PROJECT_ROOT="$HOME/Documents/Development/GitHub/mosamatic3"
SERVER_DIR="$PROJECT_ROOT/mosamatic3/server"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

cd "$SERVER_DIR"

./run-dockerbackendservices.sh

python manage.py makemigrations --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py ensure_admin

cat > /tmp/start-mosamatic-celery-tasks.sh <<EOF
#!/bin/zsh
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate mosamatic3
cd "$SERVER_DIR"
export PYTHONPATH="$PROJECT_ROOT:\$PYTHONPATH"
python -m celery -A config.celery_app worker --loglevel=info --pool=solo -Q tasks -n tasks@%h
EOF

cat > /tmp/start-mosamatic-celery-pipeline.sh <<EOF
#!/bin/zsh
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate mosamatic3
cd "$SERVER_DIR"
export PYTHONPATH="$PROJECT_ROOT:\$PYTHONPATH"
python -m celery -A config.celery_app worker --loglevel=info --pool=solo -Q pipeline -n pipeline@%h
EOF

chmod +x /tmp/start-mosamatic-celery-tasks.sh
chmod +x /tmp/start-mosamatic-celery-pipeline.sh

osascript <<EOF
tell application "Terminal"
    do script "/tmp/start-mosamatic-celery-tasks.sh"
    do script "/tmp/start-mosamatic-celery-pipeline.sh"
end tell
EOF

python manage.py runserver