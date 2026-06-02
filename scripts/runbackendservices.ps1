docker compose down -v
docker compose build
docker compose up -d redis

celery -A app.celeryapp worker --loglevel=info --pool=solo