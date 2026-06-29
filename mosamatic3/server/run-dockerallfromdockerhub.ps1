$imageName = "brecheisen/mosamatic3:latest"

Write-Host "Stopping existing containers..."
docker compose down

Write-Host "Removing local images..."
docker rmi brecheisen/mosamatic3:latest
docker rmi nginx:1.27-alpine
docker rmi redis:7-alpine
docker rmi server-pipeline-worker:latest
docker rmi server-task-worker:latest
docker rmi server-web:latest
docker rmi server-worker:latest

Write-Host "Pulling latest image..."
docker pull $imageName

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker pull failed. Aborting."
    exit 1
}

Write-Host "Starting updated stack..."
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker compose up failed."
    exit 1
}

Write-Host "App is running at http://localhost:8000"
docker compose logs -f