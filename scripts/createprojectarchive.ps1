$root = "D:\SoftwareDevelopment\GitHub\mosamatic3"
$zipFilePath = "D:\SoftwareDevelopment\GitHub\mosamatic3\sources.zip"
$itemsToInclude = @(
    "mosamatic3\server\app",
    "mosamatic3\server\.env.example",
    "mosamatic3\server\dockerfile",
    "mosamatic3\server\pyproject.toml",
    "mosamatic3\ui\src",
    "mosamatic3\ui\dockerfile",
    "mosamatic3\ui\index.html",
    "mosamatic3\ui\nginx.conf",
    "mosamatic3\ui\package.json",
    "mosamatic3\ui\tsconfig.json",
    "mosamatic3\ui\vite.config.ts",
    "docker-compose.yml"
)
Set-Location $root
Compress-Archive -Path $itemsToInclude -DestinationPath $zipFilePath -Force