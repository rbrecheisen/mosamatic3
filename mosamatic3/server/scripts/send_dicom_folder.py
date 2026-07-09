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


# Use UID strings instead of importing transfer syntax constants.
# This is robust across pynetdicom/pydicom versions.
CT_TRANSFER_SYNTAXES = [
    "1.2.840.10008.1.2.1",       # Explicit VR Little Endian
    "1.2.840.10008.1.2",         # Implicit VR Little Endian
    "1.2.840.10008.1.2.2",       # Explicit VR Big Endian

    "1.2.840.10008.1.2.4.50",    # JPEG Baseline 8-bit
    "1.2.840.10008.1.2.4.51",    # JPEG Extended 12-bit
    "1.2.840.10008.1.2.4.57",    # JPEG Lossless
    "1.2.840.10008.1.2.4.70",    # JPEG Lossless SV1
    "1.2.840.10008.1.2.4.80",    # JPEG-LS Lossless
    "1.2.840.10008.1.2.4.81",    # JPEG-LS Near Lossless
    "1.2.840.10008.1.2.4.90",    # JPEG 2000 Lossless
    "1.2.840.10008.1.2.4.91",    # JPEG 2000
    "1.2.840.10008.1.2.5",       # RLE Lossless
]


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


def collect_candidate_files(folder: Path) -> list[Path]:
    """
    Fast recursive file collection.

    We intentionally do not pre-read every file here, because that doubles
    the amount of DICOM parsing and makes large sends slow. Files are checked
    inside the send loop.
    """
    return sorted(path for path in folder.rglob("*") if path.is_file())


def get_value(ds, name: str, default: str = "") -> str:
    value = getattr(ds, name, default)
    if value is None:
        return default
    return str(value)


def get_transfer_syntax(ds) -> str:
    file_meta = getattr(ds, "file_meta", None)
    if file_meta is None:
        return "unknown"

    return str(getattr(file_meta, "TransferSyntaxUID", "unknown"))


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
        "--limit",
        type=int,
        default=None,
        help="Only send the first N candidate files. Useful for testing.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed DICOM metadata to the console.",
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

    logger.info("Scanning folder recursively for candidate files...")
    files = collect_candidate_files(folder)

    if args.limit is not None:
        files = files[:args.limit]
        logger.info("Limiting send to first %s candidate files.", args.limit)

    if not files:
        logger.error("No candidate files found in: %s", folder)
        return 1

    logger.info("Found %s candidate files.", len(files))

    ae = AE(ae_title=args.calling_ae)

    # Request one presentation context per transfer syntax.
    # A DICOM peer accepts only one transfer syntax per presentation context,
    # so this is needed when sending a mixed folder with uncompressed + JPEG2000 CT files.
    for transfer_syntax in CT_TRANSFER_SYNTAXES:
        ae.add_requested_context(CTImageStorage, [transfer_syntax])

    # Be more tolerant for large sends.
    ae.acse_timeout = 60
    ae.dimse_timeout = 300
    ae.network_timeout = 300

    logger.info("Opening DICOM association...")
    assoc = ae.associate(
        args.host,
        args.port,
        ae_title=args.called_ae,
    )

    if not assoc.is_established:
        logger.error("Could not establish DICOM association.")

        if assoc.is_rejected:
            logger.error(
                "Association rejected | result=%s | source=%s | reason=%s",
                assoc.acceptor.result,
                assoc.acceptor.result_source,
                assoc.acceptor.diagnostic,
            )
        elif assoc.is_aborted:
            logger.error("Association aborted.")
        else:
            logger.error(
                "No association established. Most likely: SCP not running, wrong port, "
                "wrong AE title, firewall, or unsupported presentation context."
            )

        return 2

    logger.info("DICOM association established.")

    sent = 0
    failed = 0
    skipped = 0

    seen_series: dict[str, int] = {}

    try:
        for index, path in enumerate(files, start=1):
            # Always initialize these before any DICOM read.
            # That keeps exception logging safe even when dcmread fails.
            patient_id = "unknown"
            patient_name = ""
            study_uid = "unknown"
            series_uid = "unknown"
            sop_uid = "unknown"
            study_description = ""
            series_description = ""
            instance_number = ""
            rows = ""
            columns = ""
            transfer_syntax = "unknown"

            try:
                # First read metadata only. This is faster and avoids loading pixel data
                # just to decide whether this is a CT image.
                try:
                    meta_ds = pydicom.dcmread(
                        str(path),
                        stop_before_pixels=True,
                        force=True,
                    )
                except Exception as exc:
                    logger.exception(
                        "[%s/%s] SKIP unreadable DICOM metadata | File=%s | %s",
                        index,
                        len(files),
                        path,
                        exc,
                    )
                    skipped += 1
                    continue

                modality = get_value(meta_ds, "Modality").upper()
                patient_id = get_value(meta_ds, "PatientID", "unknown")
                patient_name = get_value(meta_ds, "PatientName", "")
                study_uid = get_value(meta_ds, "StudyInstanceUID", "unknown")
                series_uid = get_value(meta_ds, "SeriesInstanceUID", "unknown")
                sop_uid = get_value(meta_ds, "SOPInstanceUID", "unknown")
                study_description = get_value(meta_ds, "StudyDescription", "")
                series_description = get_value(meta_ds, "SeriesDescription", "")
                instance_number = get_value(meta_ds, "InstanceNumber", "")
                rows = get_value(meta_ds, "Rows", "")
                columns = get_value(meta_ds, "Columns", "")
                transfer_syntax = get_transfer_syntax(meta_ds)

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

                # Now read the full dataset for C-STORE.
                try:
                    ds = pydicom.dcmread(str(path), force=True)
                except Exception as exc:
                    logger.exception(
                        "[%s/%s] SKIP unreadable full DICOM | PatientID=%s | Series=%s | SOP=%s | File=%s | %s",
                        index,
                        len(files),
                        patient_id,
                        series_uid,
                        sop_uid,
                        path,
                        exc,
                    )
                    skipped += 1
                    continue

                # Refresh values from the full dataset, in case metadata read differed.
                modality = get_value(ds, "Modality").upper()
                patient_id = get_value(ds, "PatientID", patient_id)
                patient_name = get_value(ds, "PatientName", patient_name)
                study_uid = get_value(ds, "StudyInstanceUID", study_uid)
                series_uid = get_value(ds, "SeriesInstanceUID", series_uid)
                sop_uid = get_value(ds, "SOPInstanceUID", sop_uid)
                study_description = get_value(ds, "StudyDescription", study_description)
                series_description = get_value(ds, "SeriesDescription", series_description)
                instance_number = get_value(ds, "InstanceNumber", instance_number)
                rows = get_value(ds, "Rows", rows)
                columns = get_value(ds, "Columns", columns)
                transfer_syntax = get_transfer_syntax(ds)

                if modality != "CT":
                    logger.info(
                        "[%s/%s] SKIP non-CT after full read | Modality=%s | File=%s",
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
                    "SeriesUID=%s | SOPUID=%s | Instance=%s | Size=%sx%s | TransferSyntax=%s",
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
                    transfer_syntax,
                )

                if not assoc.is_established:
                    logger.error(
                        "[%s/%s] Association is no longer established. Stopping send loop.",
                        index,
                        len(files),
                    )
                    failed += 1
                    break

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
                    seen_series[series_uid] = seen_series.get(series_uid, 0) + 1
                else:
                    status_code = f"0x{status.Status:04X}" if status else "No status"
                    logger.error(
                        "[%s/%s] FAIL %s | PatientID=%s | Series=%s | SOP=%s | File=%s | TransferSyntax=%s",
                        index,
                        len(files),
                        status_code,
                        patient_id,
                        series_uid,
                        sop_uid,
                        path,
                        transfer_syntax,
                    )
                    failed += 1

            except Exception as exc:
                logger.exception(
                    "[%s/%s] ERROR while sending file=%s | PatientID=%s | Series=%s | SOP=%s | TransferSyntax=%s | %s",
                    index,
                    len(files),
                    path,
                    patient_id,
                    series_uid,
                    sop_uid,
                    transfer_syntax,
                    exc,
                )
                failed += 1

    finally:
        logger.info("Releasing DICOM association...")
        if assoc.is_established:
            assoc.release()
        else:
            assoc.abort()

    logger.info("")
    logger.info("DICOM send finished.")
    logger.info("Sent:    %s", sent)
    logger.info("Skipped: %s", skipped)
    logger.info("Failed:  %s", failed)

    logger.info("Detected sent series:")
    for series_uid, count in sorted(seen_series.items(), key=lambda item: item[0]):
        logger.info("  %s files | SeriesInstanceUID=%s", count, series_uid)

    logger.info("Log file written to: %s", log_path)

    return 0 if failed == 0 and sent > 0 else 3


if __name__ == "__main__":
    sys.exit(main())