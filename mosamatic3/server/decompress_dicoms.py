from pathlib import Path
import pydicom

# Change this
DICOM_DIR = Path(r"C:\\Users\\r.brecheisen\\Desktop\\Loeki")

for path in DICOM_DIR.iterdir():
    if not path.is_file():
        continue

    print(f"Decompressing: {path.name}")

    ds = pydicom.dcmread(path)

    if ds.file_meta.TransferSyntaxUID.is_compressed:
        ds.decompress(generate_instance_uid=False)
        ds.save_as(path)
        print("  done")
    else:
        print("  already uncompressed")