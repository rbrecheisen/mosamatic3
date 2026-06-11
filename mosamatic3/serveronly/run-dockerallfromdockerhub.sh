#!/bin/zsh

set -e

imageName="brecheisen/mosamatic3:latest"

echo "Stopping existing containers..."
docker compose down

echo "Removing local images..."
docker rmi brecheisen/mosamatic3:latest || true
docker rmi nginx:1.27-alpine || true
docker rmi redis:7-alpine || true
docker rmi serveronly-web:latest || true
docker rmi serveronly-worker:latest || true

echo "Pulling latest image..."
docker pull "$imageName"

echo "Starting updated stack..."
docker compose up -d

echo "App is running at http://localhost:8000"
docker compose logs -f