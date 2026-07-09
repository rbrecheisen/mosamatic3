$root = "D:\SoftwareDevelopment\GitHub\mosamatic3\mosamatic3\server"
$zipFilePath = Join-Path $root "_sources.zip"

$itemsToInclude = @(
  "config",
  "core",
  "docker",
  "scripts",
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

$excludeRoot = Join-Path $root "core\systemdatasets"

function Get-RelativeZipPath {
  param(
    [string]$BasePath,
    [string]$FullPath
  )

  $baseUri = New-Object System.Uri(($BasePath.TrimEnd('\') + '\'))
  $fileUri = New-Object System.Uri($FullPath)

  $relativeUri = $baseUri.MakeRelativeUri($fileUri)
  $relativePath = [System.Uri]::UnescapeDataString($relativeUri.ToString())

  return $relativePath.Replace("\", "/")
}

# Remove old ZIP
if (Test-Path $zipFilePath) {
  Remove-Item $zipFilePath -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::Open(
  $zipFilePath,
  [System.IO.Compression.ZipArchiveMode]::Create
)

try {
  foreach ($item in $itemsToInclude) {
    $fullPath = Join-Path $root $item

    if (Test-Path $fullPath -PathType Container) {
      Get-ChildItem $fullPath -Recurse -File |
        Where-Object {
          -not ($_.FullName.StartsWith($excludeRoot, [System.StringComparison]::OrdinalIgnoreCase)) -and
          -not ($_.FullName -match "\\__pycache__\\") -and
          $_.Extension -ne ".pyc"
        } |
        ForEach-Object {
          $zipEntryPath = Get-RelativeZipPath -BasePath $root -FullPath $_.FullName

          [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip,
            $_.FullName,
            $zipEntryPath
          ) | Out-Null
        }
    }
    elseif (Test-Path $fullPath -PathType Leaf) {
      $zipEntryPath = Get-RelativeZipPath -BasePath $root -FullPath $fullPath

      [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip,
        $fullPath,
        $zipEntryPath
      ) | Out-Null
    }
    else {
      Write-Warning "Skipping missing item: $item"
    }
  }
}
finally {
  $zip.Dispose()
}

Write-Host "Created ZIP: $zipFilePath"