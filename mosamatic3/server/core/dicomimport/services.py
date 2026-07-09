import logging
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.datasets.services import (
    dataset_upload_root,
    make_unique_dataset_name,
    safe_relative_path,
)
from core.models import (
    Dataset,
    DatasetFile,
    DicomImportFile,
    DicomImportSession,
)
from core.pipelines.service import create_pipeline_run

logger = logging.getLogger(__name__)


def clean_path_part(value: object, fallback: str) -> str:
    text = str(value or "").strip() or fallback
    cleaned = "".join(
        char if char.isalnum() or char in ("-", "_", ".") else "_"
        for char in text
    ).strip("._")
    return cleaned or fallback


def get_dicom_import_owner() -> User:
    username = settings.DICOM_IMPORT_OWNER_USERNAME
    user = User.objects.filter(username=username).first()
    if user is None:
        raise RuntimeError(
            f"DICOM import owner user does not exist: {username!r}"
        )
    return user


def dicom_inbox_session_root(session: DicomImportSession) -> Path:
    return settings.DICOM_INBOX_ROOT / str(session.id)


def dicom_inbox_file_path(session: DicomImportSession, relative_path: str) -> Path:
    return dicom_inbox_session_root(session) / safe_relative_path(relative_path)


def _get_float_z(ds) -> float | None:
    try:
        ipp = getattr(ds, "ImagePositionPatient", None)
        if ipp is None or len(ipp) < 3:
            return None
        return float(ipp[2])
    except Exception:
        return None


def _get_int(value) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _get_or_create_session_for_dataset(
    *,
    ds,
    owner: User,
    calling_ae_title: str,
    called_ae_title: str,
) -> DicomImportSession:
    study_uid = str(getattr(ds, "StudyInstanceUID", "") or "").strip()
    series_uid = str(getattr(ds, "SeriesInstanceUID", "") or "").strip()

    if not study_uid:
        raise ValueError("Incoming DICOM misses StudyInstanceUID")
    if not series_uid:
        raise ValueError("Incoming DICOM misses SeriesInstanceUID")

    now = timezone.now()

    defaults = {
        "status": DicomImportSession.STATUS_RECEIVING,
        "calling_ae_title": calling_ae_title,
        "called_ae_title": called_ae_title,
        "patient_id": str(getattr(ds, "PatientID", "") or ""),
        "patient_name": str(getattr(ds, "PatientName", "") or ""),
        "study_description": str(getattr(ds, "StudyDescription", "") or ""),
        "series_description": str(getattr(ds, "SeriesDescription", "") or ""),
        "modality": str(getattr(ds, "Modality", "") or ""),
        "first_file_received_at": now,
        "last_file_received_at": now,
        "updated_at": now,
    }

    session, created = DicomImportSession.objects.get_or_create(
        owner=owner,
        study_instance_uid=study_uid,
        series_instance_uid=series_uid,
        defaults=defaults,
    )

    if not created:
        session.status = DicomImportSession.STATUS_RECEIVING
        session.calling_ae_title = calling_ae_title
        session.called_ae_title = called_ae_title
        session.last_file_received_at = now
        session.updated_at = now

        # Fill blanks, but do not overwrite already-known values with blanks.
        for field in [
            "patient_id",
            "patient_name",
            "study_description",
            "series_description",
            "modality",
        ]:
            if not getattr(session, field):
                setattr(session, field, defaults[field])

        session.save()

    return session


def store_incoming_dicom_dataset(
    *,
    ds,
    file_meta,
    calling_ae_title: str = "",
    called_ae_title: str = "",
) -> DicomImportSession:
    """
    Called by the DICOM Storage SCP for every C-STORE instance.

    Important design choice:
    - We ignore any original PACS/export folder structure.
    - We group by SeriesInstanceUID.
    - Every DICOM series gets one import session.
    - Files are saved as <SOPInstanceUID>.dcm.
    """

    owner = get_dicom_import_owner()
    ds.file_meta = file_meta

    modality = str(getattr(ds, "Modality", "") or "")
    if modality and modality.upper() != "CT":
        raise ValueError(f"Only CT DICOM objects are accepted for now; got Modality={modality}")

    sop_uid = str(getattr(ds, "SOPInstanceUID", "") or "").strip()
    if not sop_uid:
        raise ValueError("Incoming DICOM misses SOPInstanceUID")

    with transaction.atomic():
        session = _get_or_create_session_for_dataset(
            ds=ds,
            owner=owner,
            calling_ae_title=calling_ae_title,
            called_ae_title=called_ae_title,
        )

        relative_path = f"incoming/{clean_path_part(sop_uid, 'instance')}.dcm"
        target_path = dicom_inbox_file_path(session, relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        ds.save_as(str(target_path), write_like_original=False)
        size_bytes = target_path.stat().st_size

        DicomImportFile.objects.update_or_create(
            session=session,
            sop_instance_uid=sop_uid,
            defaults={
                "relative_path": relative_path,
                "size_bytes": size_bytes,
                "instance_number": _get_int(getattr(ds, "InstanceNumber", None)),
                "image_position_patient_z": _get_float_z(ds),
                "received_at": timezone.now(),
            },
        )

        file_qs = session.files.all()
        session.file_count = file_qs.count()
        session.total_size_bytes = sum(file_qs.values_list("size_bytes", flat=True))
        session.last_file_received_at = timezone.now()
        session.updated_at = timezone.now()
        session.save(
            update_fields=[
                "file_count",
                "total_size_bytes",
                "last_file_received_at",
                "updated_at",
                "status",
            ]
        )

    return session


def mark_stable_imports_ready() -> int:
    """
    Called manually or by a delayed Celery task later.
    For now this makes imports reviewable when no file arrived recently.
    """

    cutoff = timezone.now() - timezone.timedelta(
        seconds=settings.DICOM_IMPORT_STABLE_SECONDS
    )

    qs = DicomImportSession.objects.filter(
        status=DicomImportSession.STATUS_RECEIVING,
        last_file_received_at__lte=cutoff,
    )

    count = 0
    for session in qs:
        session.status = DicomImportSession.STATUS_READY
        session.ready_at = timezone.now()
        session.updated_at = timezone.now()
        session.save(update_fields=["status", "ready_at", "updated_at"])
        count += 1

    return count


def make_dataset_name_for_import(session: DicomImportSession) -> str:
    patient = session.patient_id or "unknown_patient"
    series = session.series_description or session.series_instance_uid
    timestamp = timezone.localtime(session.created_at).strftime("%Y%m%d_%H%M%S")
    return f"DICOM PACS import - {patient} - {series} - {timestamp}"


def create_dataset_from_import_session(session: DicomImportSession) -> Dataset:
    """
    Converts the reviewable DICOM inbox session into a normal input Dataset.

    Critical TotalSegmentator/slice-select compatibility:
    all files from this one SeriesInstanceUID are placed into one folder:

        <PatientID>/<SeriesInstanceUID>/*.dcm
    """

    if session.dataset_id:
        return session.dataset

    if session.status not in [
        DicomImportSession.STATUS_READY,
        DicomImportSession.STATUS_DATASET_CREATED,
    ]:
        raise ValidationError(
            f"Import must be ready before creating a dataset. Current status: {session.status}"
        )

    if session.file_count == 0:
        raise ValidationError("Cannot create a dataset from an empty DICOM import.")

    session.status = DicomImportSession.STATUS_CREATING_DATASET
    session.updated_at = timezone.now()
    session.save(update_fields=["status", "updated_at"])

    dataset_root = None

    try:
        with transaction.atomic():
            dataset = Dataset.objects.create(
                owner=session.owner,
                name=make_unique_dataset_name(
                    make_dataset_name_for_import(session),
                    session.owner,
                ),
                kind=Dataset.KIND_INPUT,
                status="ready",
            )

            dataset_root = dataset_upload_root(session.owner_id, dataset.id)
            dataset_root.mkdir(parents=True, exist_ok=False)

            patient_folder = clean_path_part(session.patient_id, "unknown_patient")
            series_folder = clean_path_part(
                session.series_instance_uid,
                "unknown_series",
            )

            for import_file in session.files.all():
                source_path = dicom_inbox_file_path(
                    session,
                    import_file.relative_path,
                )

                prefix = ""
                if import_file.instance_number is not None:
                    prefix = f"{import_file.instance_number:05d}_"

                target_relative_path = (
                    Path(patient_folder)
                    / series_folder
                    / f"{prefix}{clean_path_part(import_file.sop_instance_uid, 'instance')}.dcm"
                )

                target_relative_path = safe_relative_path(
                    target_relative_path.as_posix()
                )

                target_path = dataset_root / target_relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(source_path, target_path)

                DatasetFile.objects.create(
                    dataset=dataset,
                    relative_path=target_relative_path.as_posix(),
                    size_bytes=target_path.stat().st_size,
                )

            session.dataset = dataset
            session.status = DicomImportSession.STATUS_DATASET_CREATED
            session.updated_at = timezone.now()
            session.save(update_fields=["dataset", "status", "updated_at"])

            return dataset

    except Exception as exc:
        if dataset_root is not None:
            shutil.rmtree(dataset_root, ignore_errors=True)

        session.status = DicomImportSession.STATUS_FAILED
        session.error_message = str(exc)
        session.updated_at = timezone.now()
        session.save(update_fields=["status", "error_message", "updated_at"])
        raise


def start_l3_pipeline_for_import(session: DicomImportSession):
    dataset = create_dataset_from_import_session(session)

    system_dataset = Dataset.objects.filter(
        owner=session.owner,
        name=settings.BUILTIN_MODEL_FILES_DATASET_NAME,
        is_system=True,
        kind=Dataset.KIND_INPUT,
    ).first()

    if system_dataset is None:
        raise ValidationError(
            f"System model files dataset not found: {settings.BUILTIN_MODEL_FILES_DATASET_NAME}"
        )

    pipeline_run = create_pipeline_run(
        user=session.owner,
        config_key=settings.DICOM_IMPORT_PIPELINE_KEY,
        initial_dataset_id=dataset.id,
        overrides={
            "steps": {
                "segment": {
                    "parameters": {
                        "model_files_dataset_id": str(system_dataset.id),
                    }
                }
            }
        },
    )

    session.pipeline_run = pipeline_run
    session.status = DicomImportSession.STATUS_PIPELINE_QUEUED
    session.updated_at = timezone.now()
    session.save(update_fields=["pipeline_run", "status", "updated_at"])

    return pipeline_run


def delete_import_session(session: DicomImportSession) -> None:
    if session.pipeline_run_id:
        raise ValidationError("Cannot delete a DICOM import that has a pipeline run.")

    root = dicom_inbox_session_root(session)
    session.status = DicomImportSession.STATUS_DELETED
    session.updated_at = timezone.now()
    session.save(update_fields=["status", "updated_at"])

    session.delete()
    shutil.rmtree(root, ignore_errors=True)


def update_dicom_import_status_from_pipeline_run(pipeline_run) -> None:
    """
    Keep linked DICOM import session status in sync with the final pipeline status.
    """

    from core.models import DicomImportSession, PipelineRun

    session = DicomImportSession.objects.filter(
        pipeline_run=pipeline_run,
    ).first()

    if session is None:
        return

    if pipeline_run.status == PipelineRun.STATUS_SUCCESS:
        session.status = DicomImportSession.STATUS_DONE
        session.error_message = ""
    elif pipeline_run.status == PipelineRun.STATUS_FAILURE:
        session.status = DicomImportSession.STATUS_FAILED
        session.error_message = pipeline_run.error_message or "Pipeline failed."
    elif pipeline_run.status == PipelineRun.STATUS_CANCELED:
        session.status = DicomImportSession.STATUS_FAILED
        session.error_message = "Pipeline was canceled."
    elif pipeline_run.status == PipelineRun.STATUS_RUNNING:
        session.status = DicomImportSession.STATUS_PROCESSING
    else:
        return

    session.updated_at = timezone.now()
    session.save(update_fields=["status", "error_message", "updated_at"])