#!/bin/zsh

docker compose down
docker compose build
docker compose up -d redis

conda activate mosamatic3
celery -A app.celeryapp worker --loglevel=info --pool=solo
