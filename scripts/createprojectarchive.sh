#!/bin/zsh

root="$HOME/Documents/Development/GitHub/mosamatic3"
zipFilePath="$root/sources.zip"

itemsToInclude=(
  "mosamatic3/serveronly/config"
  "mosamatic3/serveronly/core"
  "mosamatic3/serveronly/static"
  "mosamatic3/serveronly/templates"
  "mosamatic3/serveronly/.env.example"
  "mosamatic3/serveronly/docker-compose.yml"
  "mosamatic3/serveronly/Dockerfile"
  "mosamatic3/serveronly/manage.py"
  "mosamatic3/serveronly/pyproject.toml"
)

cd "$root" || exit 1

rm -f "$zipFilePath"

zip -r "$zipFilePath" "${itemsToInclude[@]}"