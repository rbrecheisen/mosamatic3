$root = "D:\SoftwareDevelopment\GitHub\mosamatic3\mosamatic3\serveronly"
$zipFilePath = "D:\SoftwareDevelopment\GitHub\mosamatic3\mosamatic3\serveronly\archive.zip"

$itemsToInclude = @(
  "config",
  "core",
  "docker",
  "nginx",
  "static",
  "templates",
  ".env.example",
  "docker-compose.yml",
  "docker-compose-dev.yml",
  "Dockerfile",
  "manage.py",
  "pyproject.toml",
  "uv.lock"
)

Set-Location $root
Compress-Archive -Path $itemsToInclude -DestinationPath $zipFilePath -Force