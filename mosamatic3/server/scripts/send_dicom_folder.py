#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

import pydicom
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage


def is_dicom_file(path: Path) -> bool:
    if not path.is_file():
        return False

    try:
        pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
        return True
    except Exception:
        return False


def collect_dicom_files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if is_dicom_file(path)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Push a local DICOM folder to Mosamatic3 using DICOM C-STORE."
    )

    parser.add_argument(
        "folder",
        type=Path,
        help="Folder containing DICOM files. Subfolders are scanned recursively.",
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Mosamatic3 DICOM SCP host. Default: 127.0.0.1",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=11112,
        help="Mosamatic3 DICOM SCP port. Default: 11112",
    )

    parser.add_argument(
        "--called-ae",
        default="MOSAMATIC3",
        help="Called AE title configured in Mosamatic3. Default: MOSAMATIC3",
    )

    parser.add_argument(
        "--calling-ae",
        default="MOSATEST",
        help="Calling AE title used by this sender. Default: MOSATEST",
    )

    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()

    if not folder.exists() or not folder.is_dir():
        print(f"ERROR: Folder does not exist or is not a directory: {folder}")
        return 1

    files = collect_dicom_files(folder)

    if not files:
        print(f"ERROR: No readable DICOM files found in: {folder}")
        return 1

    print(f"Found {len(files)} DICOM files.")
    print(f"Connecting to {args.host}:{args.port} as {args.calling_ae} -> {args.called_ae}")

    ae = AE(ae_title=args.calling_ae)

    # First implementation matches your Mosamatic3 SCP: CT only.
    ae.add_requested_context(CTImageStorage)

    assoc = ae.associate(
        args.host,
        args.port,
        ae_title=args.called_ae,
    )

    if not assoc.is_established:
        print("ERROR: Could not establish DICOM association.")
        return 2

    sent = 0
    failed = 0
    skipped = 0

    try:
        for index, path in enumerate(files, start=1):
            try:
                ds = pydicom.dcmread(str(path), force=True)

                modality = str(getattr(ds, "Modality", "") or "").upper()
                if modality != "CT":
                    print(f"[{index}/{len(files)}] SKIP non-CT: {path}")
                    skipped += 1
                    continue

                sop_uid = getattr(ds, "SOPInstanceUID", "unknown")
                series_uid = getattr(ds, "SeriesInstanceUID", "unknown")

                status = assoc.send_c_store(ds)

                if status and status.Status == 0x0000:
                    print(
                        f"[{index}/{len(files)}] OK "
                        f"Series={series_uid} SOP={sop_uid}"
                    )
                    sent += 1
                else:
                    status_code = f"0x{status.Status:04X}" if status else "No status"
                    print(
                        f"[{index}/{len(files)}] FAIL {status_code}: {path}"
                    )
                    failed += 1

            except Exception as exc:
                print(f"[{index}/{len(files)}] ERROR {path}: {exc}")
                failed += 1

    finally:
        assoc.release()

    print()
    print("Done.")
    print(f"Sent:    {sent}")
    print(f"Skipped: {skipped}")
    print(f"Failed:  {failed}")

    return 0 if failed == 0 and sent > 0 else 3


if __name__ == "__main__":
    sys.exit(main())