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
  "run-dockerall.ps1",
  "run-dockerallfromdockerhub.ps1",
  "run-dockerdeploy2hub.ps1",
  "run-dockerstop.ps1",
  "run-server.ps1",
  "run-setupenv.ps1",
  "run-tests.ps1",
  "run-uvinstall.ps1",
  "run-uvsync.ps1",
  "Dockerfile",
  "manage.py",
  "pyproject.toml",
  "uv.lock"
)

Set-Location $root
Compress-Archive -Path $itemsToInclude -DestinationPath $zipFilePath -Force