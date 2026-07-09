#!/bin/zsh

set -e

root="$HOME/Documents/Development/GitHub/mosamatic3/mosamatic3/server"
zipFilePath="$root/_sources.zip"

itemsToInclude=(
  "config"
  "core"
  "docker"
  "scripts"
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

# Build the ZIP from the project root so paths are preserved.
# Exclude:
# - built-in/system model datasets
# - Python cache files
# - existing generated ZIP
zip -r "$zipFilePath" "${itemsToInclude[@]}" \
  -x "core/systemdatasets/*" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x "_sources.zip"

echo "Created ZIP: $zipFilePath"
echo ""
echo "First entries:"
unzip -l "$zipFilePath" | head -n 40