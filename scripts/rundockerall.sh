#!/bin/zsh

docker compose down -v
docker compose build
docker compose up -d
docker compose logs -f
