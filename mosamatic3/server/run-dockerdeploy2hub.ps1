docker compose -f docker-compose-dev.yml down
docker build --no-cache -t brecheisen/mosamatic3:latest .
docker logout
type C:\\Users\\r.brecheisen\\dockerhub.txt | docker login --username brecheisen --password-stdin
docker push brecheisen/mosamatic3:latest