#!/usr/bin/env python3

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pydicom
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage


logger = logging.getLogger("send_dicom_folder")


def setup_logging(log_dir: Path, verbose: bool) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"send_dicom_folder_{timestamp}.log"

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return log_path


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


def collect_dicom_files_quickly(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file()
    )


def get_value(ds, name: str, default: str = "") -> str:
    value = getattr(ds, name, default)
    if value is None:
        return default
    return str(value)


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

    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Directory where the send log is written. Default: logs",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print more detailed DICOM metadata to the console.",
    )

    args = parser.parse_args()

    log_path = setup_logging(args.log_dir, args.verbose)

    folder = args.folder.expanduser().resolve()

    logger.info("DICOM send started")
    logger.info("Log file: %s", log_path)
    logger.info("Source folder: %s", folder)
    logger.info(
        "Target: %s:%s | Calling AE: %s | Called AE: %s",
        args.host,
        args.port,
        args.calling_ae,
        args.called_ae,
    )

    if not folder.exists() or not folder.is_dir():
        logger.error("Folder does not exist or is not a directory: %s", folder)
        return 1

    logger.info("Scanning folder recursively for DICOM files...")
    files = collect_dicom_files_quickly(folder)

    if not files:
        logger.error("No readable DICOM files found in: %s", folder)
        return 1

    logger.info("Found %s readable DICOM files.", len(files))

    ae = AE(ae_title=args.calling_ae)

    # First implementation matches Mosamatic3 SCP: CT only.
    ae.add_requested_context(CTImageStorage)

    logger.info("Opening DICOM association...")
    assoc = ae.associate(
        args.host,
        args.port,
        ae_title=args.called_ae,
    )

    if not assoc.is_established:
        logger.error("Could not establish DICOM association.")
        return 2

    logger.info("DICOM association established.")

    sent = 0
    failed = 0
    skipped = 0

    seen_series: dict[str, int] = {}

    try:
        for index, path in enumerate(files, start=1):
            try:
                ds = pydicom.dcmread(str(path), force=True)

                modality = get_value(ds, "Modality").upper()
                patient_id = get_value(ds, "PatientID", "unknown")
                patient_name = get_value(ds, "PatientName", "")
                study_uid = get_value(ds, "StudyInstanceUID", "unknown")
                series_uid = get_value(ds, "SeriesInstanceUID", "unknown")
                sop_uid = get_value(ds, "SOPInstanceUID", "unknown")
                study_description = get_value(ds, "StudyDescription", "")
                series_description = get_value(ds, "SeriesDescription", "")
                instance_number = get_value(ds, "InstanceNumber", "")
                rows = get_value(ds, "Rows", "")
                columns = get_value(ds, "Columns", "")

                seen_series[series_uid] = seen_series.get(series_uid, 0) + 1

                if modality != "CT":
                    logger.info(
                        "[%s/%s] SKIP non-CT | Modality=%s | File=%s",
                        index,
                        len(files),
                        modality or "unknown",
                        path,
                    )
                    skipped += 1
                    continue

                logger.debug(
                    "[%s/%s] Sending file=%s | PatientID=%s | PatientName=%s | "
                    "StudyDescription=%s | SeriesDescription=%s | StudyUID=%s | "
                    "SeriesUID=%s | SOPUID=%s | Instance=%s | Size=%sx%s",
                    index,
                    len(files),
                    path,
                    patient_id,
                    patient_name,
                    study_description,
                    series_description,
                    study_uid,
                    series_uid,
                    sop_uid,
                    instance_number,
                    rows,
                    columns,
                )

                status = assoc.send_c_store(ds)

                if status and status.Status == 0x0000:
                    logger.info(
                        "[%s/%s] OK | PatientID=%s | Series=%s | Instance=%s | SOP=%s",
                        index,
                        len(files),
                        patient_id,
                        series_uid,
                        instance_number or "-",
                        sop_uid,
                    )
                    sent += 1
                else:
                    status_code = f"0x{status.Status:04X}" if status else "No status"
                    logger.error(
                        "[%s/%s] FAIL %s | PatientID=%s | Series=%s | SOP=%s | File=%s",
                        index,
                        len(files),
                        status_code,
                        patient_id,
                        series_uid,
                        sop_uid,
                        path,
                    )
                    failed += 1

            except Exception as exc:
                logger.exception(
                    "[%s/%s] ERROR while sending file=%s | %s",
                    index,
                    len(files),
                    path,
                    exc,
                )
                failed += 1

    finally:
        logger.info("Releasing DICOM association...")
        assoc.release()

    logger.info("")
    logger.info("DICOM send finished.")
    logger.info("Sent:    %s", sent)
    logger.info("Skipped: %s", skipped)
    logger.info("Failed:  %s", failed)

    logger.info("Detected series:")
    for series_uid, count in sorted(seen_series.items(), key=lambda item: item[0]):
        logger.info("  %s files | SeriesInstanceUID=%s", count, series_uid)

    logger.info("Log file written to: %s", log_path)

    return 0 if failed == 0 and sent > 0 else 3


if __name__ == "__main__":
    sys.exit(main())