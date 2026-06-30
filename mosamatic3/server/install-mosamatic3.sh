#!/bin/zsh

set -e

INSTALL_DIR="$HOME/mosamatic3"
COMPOSE_URL="https://raw.githubusercontent.com/YOURUSER/YOURREPO/main/docker-compose.yml"

echo "Checking Docker..."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker command not found."
  echo "Please install Docker Desktop first:"
  echo "https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop does not seem to be running."
  echo "Please start Docker Desktop first and run this installer again."
  exit 1
fi

echo "Creating install directory..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR" || exit 1

echo "Downloading docker-compose.yml..."
curl -L "$COMPOSE_URL" -o docker-compose.yml

echo "Pulling Docker images..."
docker compose pull

echo "Starting Mosamatic3..."
docker compose up -d

echo ""
echo "Mosamatic3 is now running."
echo "Open the app at:"
echo "http://localhost:8000"