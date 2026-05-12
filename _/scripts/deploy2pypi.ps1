#requires -Version 5.1
$ErrorActionPreference = "Stop"

$confirm = Read-Host "Did you update the CHANGELOG? (y/n)"
if ($confirm -notmatch '^(?i)y$') {
    Write-Host "Aborting deployment"
    exit 1
}

$bumpLevel = Read-Host "What version bump level do you want to use? [major, minor, patch (default)]"

if ($bumpLevel -match '^(?i)major$') {
    python scripts\bumpversion.py --part major --update_toml 1
} elseif ($bumpLevel -match '^(?i)minor$') {
    python scripts\bumpversion.py --part minor --update_toml 1
} else {
    python scripts\bumpversion.py --part patch --update_toml 1
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Version bump failed." -ForegroundColor Red
    exit 1
}

$VERSION = (Get-Content VERSION -Raw).Trim()
Write-Host "New version: $VERSION. Is this correct?"
Read-Host "Press Enter to continue"

Copy-Item -Path "VERSION" -Destination ".\src\mosamatic2\ui\resources\" -Force

$TOKEN = (Get-Content "G:\My Drive\data\ApiKeysAndPasswordFiles\pypi-token.txt" -Raw).Trim()
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = $TOKEN

git add -A
if ($LASTEXITCODE -ne 0) { exit 1 }

git commit -m "Deploying version $VERSION"
if ($LASTEXITCODE -ne 0) { exit 1 }

git push
if ($LASTEXITCODE -ne 0) { exit 1 }

# Remove build artifacts if they exist
$pathsToRemove = @(
    "dist",
    "build",
    "src\mosamaticinsights.egg-info"
)
foreach ($p in $pathsToRemove) {
    if (Test-Path $p) {
        Remove-Item $p -Recurse -Force
    }
}

python -m build
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed." -ForegroundColor Red
    exit 1
}

python -m twine upload dist/*
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Twine upload failed." -ForegroundColor Red
    exit 1
}