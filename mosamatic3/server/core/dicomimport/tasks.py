from django.conf import settings
from django.utils import timezone

from config.celery_app import app
from core.models import DicomImportSession
from .services import mark_stable_imports_ready


@app.task(name="core.dicomimport.tasks.mark_stable_imports_ready")
def mark_stable_imports_ready_task() -> dict:
    count = mark_stable_imports_ready()
    return {"ready_count": count}


@app.task(name="core.dicomimport.tasks.finalize_import_if_stable")
def finalize_import_if_stable(session_id: str) -> dict:
    session = DicomImportSession.objects.filter(id=session_id).first()

    if session is None:
        return {"status": "missing"}

    if session.status != DicomImportSession.STATUS_RECEIVING:
        return {"status": session.status}

    if session.last_file_received_at is None:
        return {"status": "no_files"}

    age_seconds = (
        timezone.now() - session.last_file_received_at
    ).total_seconds()

    if age_seconds < settings.DICOM_IMPORT_STABLE_SECONDS:
        return {
            "status": "not_stable_yet",
            "age_seconds": age_seconds,
        }

    session.status = DicomImportSession.STATUS_READY
    session.ready_at = timezone.now()
    session.updated_at = timezone.now()
    session.save(update_fields=["status", "ready_at", "updated_at"])

    return {
        "status": "ready_for_review",
        "session_id": str(session.id),
    }