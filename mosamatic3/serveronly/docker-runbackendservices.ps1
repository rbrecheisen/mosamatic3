docker compose -f docker-compose-dev.yml down
docker compose -f docker-compose-dev.yml up -d --build redis worker
docker compose -f docker-compose-dev.yml logs -f