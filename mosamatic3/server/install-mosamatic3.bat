@echo off
set INSTALL_DIR=%USERPROFILE%\mosamatic3
set COMPOSE_URL=https://raw.githubusercontent.com/rbrecheisen/mosamatic3/refs/heads/main/mosamatic3/server/docker-compose.yml
set NGINX_CONF_URL=https://raw.githubusercontent.com/rbrecheisen/mosamatic3/refs/heads/main/mosamatic3/server/nginx/nginx.conf

docker info >nul 2>&1
if errorlevel 1 (
    echo Docker Desktop does not seem to be running.
    echo Please start Docker Desktop first and run this installer again.
    pause
    exit /b 1
)

mkdir "%INSTALL_DIR%" 2>nul
mkdir "%INSTALL_DIR%\nginx" 2>nul

cd /d "%INSTALL_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%COMPOSE_URL%' -OutFile 'docker-compose.yml'"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%NGINX_CONF_URL%' -OutFile 'nginx\nginx.conf'"

docker compose pull
docker compose up -d

pause