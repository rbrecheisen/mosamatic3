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
  "docker-deploy2hub.ps1",
  "docker-pullfromhub-runall.ps1",
  "docker-runall.ps1",
  "docker-runbackendservices.ps1",
  "Dockerfile",
  "manage.py",
  "pyproject.toml",
  "uv.lock"
)

Set-Location $root
Compress-Archive -Path $itemsToInclude -DestinationPath $zipFilePath -Force