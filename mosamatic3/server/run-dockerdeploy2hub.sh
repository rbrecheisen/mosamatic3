# #!/bin/bash

# docker compose -f docker-compose-dev.yml down
# docker build --no-cache -t brecheisen/mosamatic3:latest .
# docker logout
# type /Users/ralph/dockerhub.txt | docker login --username brecheisen --password-stdin
# docker push brecheisen/mosamatic3:latest

#!/bin/bash

set -e

IMAGE_NAME="brecheisen/mosamatic3"
DOCKERHUB_REPOSITORY="brecheisen/mosamatic3"
DOCKERHUB_USERNAME="brecheisen"
DOCKERHUB_PASSWORD_FILE="/Users/ralph/dockerhub.txt"

VERSION="$1"


get_latest_dockerhub_version() {
    echo "Checking Docker Hub for available versions..."

    URL="https://hub.docker.com/v2/repositories/${DOCKERHUB_REPOSITORY}/tags?page_size=100"

    TAGS=""

    while [ -n "$URL" ] && [ "$URL" != "null" ]; do
        RESPONSE=$(curl -fsSL "$URL")

        PAGE_TAGS=$(echo "$RESPONSE" | python3 -c '
import sys, json
data = json.load(sys.stdin)
for item in data.get("results", []):
    print(item["name"])
')

        TAGS="${TAGS}
${PAGE_TAGS}"

        URL=$(echo "$RESPONSE" | python3 -c '
import sys, json
data = json.load(sys.stdin)
print(data.get("next") or "")
')
    done

    LATEST_VERSION=$(
        echo "$TAGS" \
        | grep -E '^v?[0-9]+(\.[0-9]+){1,3}$' \
        | sed 's/^v//' \
        | sort -V \
        | tail -n 1
    )

    if [ -z "$LATEST_VERSION" ]; then
        echo "No versioned Docker images found in Docker Hub."
        return 1
    fi

    echo "$LATEST_VERSION"
}


# ----------------------------------------------------------------------
# No version supplied: show latest Docker Hub version
# ----------------------------------------------------------------------

if [ -z "$VERSION" ]; then

    LATEST_VERSION=$(get_latest_dockerhub_version)

    echo
    echo "Latest Docker Hub version: $LATEST_VERSION"
    echo "Image: ${IMAGE_NAME}:${LATEST_VERSION}"

    exit 0
fi


# ----------------------------------------------------------------------
# Validate version
# ----------------------------------------------------------------------

if ! echo "$VERSION" | grep -Eq '^v?[0-9]+(\.[0-9]+){1,3}$'; then
    echo "ERROR: Invalid version '$VERSION'."
    echo "Use something like 1.0.0 or v1.0.0."
    exit 1
fi

# Remove optional leading v to keep Docker tags consistent
VERSION="${VERSION#v}"

echo
echo "Building Mosamatic3 Docker image"
echo "Version : $VERSION"
echo "Image   : ${IMAGE_NAME}:${VERSION}"
echo


# ----------------------------------------------------------------------
# Stop development containers
# ----------------------------------------------------------------------

docker compose -f docker-compose-dev.yml down


# ----------------------------------------------------------------------
# Build once, applying both tags
# ----------------------------------------------------------------------

docker build --no-cache \
    -t "${IMAGE_NAME}:${VERSION}" \
    -t "${IMAGE_NAME}:latest" \
    .


# ----------------------------------------------------------------------
# Docker Hub login
# ----------------------------------------------------------------------

docker logout >/dev/null 2>&1 || true

cat "$DOCKERHUB_PASSWORD_FILE" \
    | docker login \
        --username "$DOCKERHUB_USERNAME" \
        --password-stdin


# ----------------------------------------------------------------------
# Push versioned image
# ----------------------------------------------------------------------

echo
echo "Pushing ${IMAGE_NAME}:${VERSION} ..."

docker push "${IMAGE_NAME}:${VERSION}"


# ----------------------------------------------------------------------
# Push latest
# ----------------------------------------------------------------------

echo
echo "Pushing ${IMAGE_NAME}:latest ..."

docker push "${IMAGE_NAME}:latest"


echo
echo "Done."
echo
echo "Published:"
echo "  ${IMAGE_NAME}:${VERSION}"
echo "  ${IMAGE_NAME}:latest"