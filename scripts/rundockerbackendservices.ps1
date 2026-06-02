docker compose down
docker compose build
docker compose up -d redis worker
docker compose logs -f