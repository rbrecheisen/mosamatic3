conda activate mosamatic3

$ErrorActionPreference = "Stop"

python scripts\send_dicom_folder.py `
  "G:\My Drive\data\Mosamatic\testdata\CT" `
  --host 127.0.0.1 `
  --port 11112 `
  --called-ae MOSAMATIC3