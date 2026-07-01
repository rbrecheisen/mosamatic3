#!/bin/zsh

set -e

cd "$(dirname "$0")"

echo "Running Mosamatic3..."
echo ""

zsh ./run-mosamatic3.sh

echo ""
echo "Done"
echo "You can close this window."

echo ""
read -k 1 "?Press any key to close..."
