docker compose -f docker-compose-dev.yml down
docker compose -f docker-compose-dev.yml up -d --build

powershell -NoProfile -ExecutionPolicy Bypass -Command "docker compose -f docker-compose-dev.yml logs -f --no-color 2>&1 | Tee-Object -FilePath '.\data\logs\docker-compose.log' -Append"