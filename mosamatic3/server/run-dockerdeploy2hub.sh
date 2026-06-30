#!/bin/zsh

docker compose -f docker-compose-dev.yml down -v
docker build --no-cache -t brecheisen/mosamatic3:latest .
docker logout
type /Users/ralph/dockerhub.txt | docker login --username brecheisen --password-stdin
docker push brecheisen/mosamatic3:latest