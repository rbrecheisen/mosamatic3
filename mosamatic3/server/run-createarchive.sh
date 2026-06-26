#!/bin/zsh

root="$HOME/Documents/Development/GitHub/mosamatic3/mosamatic3/server"
zipFilePath="$root/sources.zip"

itemsToInclude=(
  "config"
  "core"
  "docker"
  "nginx"
  "static"
  "templates"
  ".env.example"
  "docker-compose.yml"
  "docker-compose-dev.yml"
  "run-dockerall.sh"
  "run-dockerallfromdockerhub.sh"
  "run-dockerdeploy2hub.sh"
  "run-dockerstop.sh"
  "run-server.sh"
  "run-setupenv.sh"
  "run-tests.sh"
  "run-uvinstall.sh"
  "run-uvsync.sh"
  "Dockerfile"
  "manage.py"
  "pyproject.toml"
  "uv.lock"
)

cd "$root" || exit 1
rm -f "$zipFilePath"
zip -r "$zipFilePath" "${itemsToInclude[@]}"