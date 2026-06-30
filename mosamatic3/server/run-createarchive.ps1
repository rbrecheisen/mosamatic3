$root = "D:\SoftwareDevelopment\GitHub\mosamatic3\mosamatic3\server"
$zipFilePath = "D:\SoftwareDevelopment\GitHub\mosamatic3\mosamatic3\server\_sources.zip"

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

$excludeRoot = Join-Path $root "core\systemdatasets"

$filesToZip = foreach ($item in $itemsToInclude) {
  $fullPath = Join-Path $root $item

  if (Test-Path $fullPath -PathType Container) {
    Get-ChildItem $fullPath -Recurse -File |
      Where-Object {
        -not ($_.FullName.StartsWith($excludeRoot, [System.StringComparison]::OrdinalIgnoreCase))
      }
  }
  elseif (Test-Path $fullPath -PathType Leaf) {
    Get-Item $fullPath
  }
}

Compress-Archive -Path $filesToZip.FullName -DestinationPath $zipFilePath -Force