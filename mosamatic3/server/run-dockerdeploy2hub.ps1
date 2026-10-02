param(
    [Parameter(Position = 0)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

$ImageName = "brecheisen/mosamatic3"
$DockerHubRepository = "brecheisen/mosamatic3"
$DockerHubUsername = "brecheisen"
$DockerHubPasswordFile = "C:\Users\r.brecheisen\dockerhub.txt"


function Get-LatestDockerHubVersion {
    Write-Host "Checking Docker Hub for available versions..."

    $url = "https://hub.docker.com/v2/repositories/$DockerHubRepository/tags?page_size=100"
    $tags = @()

    while ($url) {
        $response = Invoke-RestMethod -Uri $url -Method Get

        $tags += $response.results.name
        $url = $response.next
    }

    # Accept version tags such as:
    # 1.0
    # 1.0.0
    # 2.3.4
    # v1.2.3
    $versions = $tags |
        Where-Object { $_ -match '^v?(\d+(?:\.\d+){1,3})$' } |
        ForEach-Object {
            [PSCustomObject]@{
                Tag     = $_
                Version = [version]($_ -replace '^v', '')
            }
        } |
        Sort-Object Version -Descending

    if (-not $versions) {
        Write-Host "No versioned Docker images found in Docker Hub."
        return
    }

    return $versions[0].Tag
}


# ----------------------------------------------------------------------
# No version parameter: only show latest Docker Hub version
# ----------------------------------------------------------------------

if ([string]::IsNullOrWhiteSpace($Version)) {

    $latestVersion = Get-LatestDockerHubVersion

    if ($latestVersion) {
        Write-Host ""
        Write-Host "Latest Docker Hub version: $latestVersion"
        Write-Host "Image: ${ImageName}:$latestVersion"
    }

    exit 0
}


# ----------------------------------------------------------------------
# Version supplied: validate, build, tag and push
# ----------------------------------------------------------------------

$Version = $Version.Trim()

if ($Version -notmatch '^v?\d+(?:\.\d+){1,3}$') {
    Write-Error "Invalid version '$Version'. Use something like 1.0.0 or v1.0.0."
    exit 1
}

Write-Host ""
Write-Host "Building Mosamatic3 Docker image"
Write-Host "Version : $Version"
Write-Host "Image   : ${ImageName}:$Version"
Write-Host ""

docker compose -f docker-compose-dev.yml down

if ($LASTEXITCODE -ne 0) {
    throw "docker compose down failed."
}


# Build once and assign both tags to exactly the same image
docker build --no-cache `
    -t "${ImageName}:$Version" `
    -t "${ImageName}:latest" `
    .

if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed."
}


# ----------------------------------------------------------------------
# Docker Hub login
# ----------------------------------------------------------------------

docker logout | Out-Null

Get-Content $DockerHubPasswordFile -Raw |
    docker login --username $DockerHubUsername --password-stdin

if ($LASTEXITCODE -ne 0) {
    throw "Docker Hub login failed."
}


# ----------------------------------------------------------------------
# Push versioned image
# ----------------------------------------------------------------------

Write-Host ""
Write-Host "Pushing ${ImageName}:$Version ..."

docker push "${ImageName}:$Version"

if ($LASTEXITCODE -ne 0) {
    throw "Failed to push ${ImageName}:$Version."
}


# ----------------------------------------------------------------------
# Push latest
# ----------------------------------------------------------------------

Write-Host ""
Write-Host "Pushing ${ImageName}:latest ..."

docker push "${ImageName}:latest"

if ($LASTEXITCODE -ne 0) {
    throw "Failed to push ${ImageName}:latest."
}


Write-Host ""
Write-Host "Done."
Write-Host ""
Write-Host "Published:"
Write-Host "  ${ImageName}:$Version"
Write-Host "  ${ImageName}:latest"