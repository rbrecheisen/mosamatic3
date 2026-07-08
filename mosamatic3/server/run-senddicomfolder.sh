#!/bin/zsh

set -e

cd "$HOME/Documents/Development/GitHub/mosamatic3/mosamatic3/server" || exit 1

python scripts/send_dicom_folder.py \
  "/Users/ralph/Library/CloudStorage/GoogleDrive-ralph.brecheisen@gmail.com/My Drive/data/Mosamatic/testdata/CT" \
  --host 127.0.0.1 \
  --port 11112 \
  --called-ae MOSAMATIC3