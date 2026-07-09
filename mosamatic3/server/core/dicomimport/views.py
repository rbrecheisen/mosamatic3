from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import DicomImportSession
from .services import (
    create_dataset_from_import_session,
    delete_all_import_sessions,
    delete_import_session,
    mark_stable_imports_ready,
    start_l3_pipeline_for_import,
)


@login_required
def dicom_imports_page(request):
    # Useful while testing: visiting the page also moves stable imports to Ready.
    mark_stable_imports_ready()

    sessions = (
        DicomImportSession.objects
        .filter(owner=request.user)
        .select_related("dataset", "pipeline_run")
        .prefetch_related("files")
        .order_by("-last_file_received_at", "-created_at")
    )

    return render(
        request,
        "dicomimport/dicom_imports.html",
        {
            "sessions": sessions,
        },
    )


@login_required
def dicom_import_detail_page(request, session_id):
    mark_stable_imports_ready()

    session = get_object_or_404(
        DicomImportSession.objects
        .select_related("dataset", "pipeline_run")
        .prefetch_related("files"),
        id=session_id,
        owner=request.user,
    )

    return render(
        request,
        "dicomimport/dicom_import_detail.html",
        {
            "session": session,
            "files": session.files.all()[:500],
        },
    )


@login_required
@require_POST
def create_dataset_view(request, session_id):
    session = get_object_or_404(
        DicomImportSession,
        id=session_id,
        owner=request.user,
    )

    try:
        dataset = create_dataset_from_import_session(session)
        messages.success(request, f"Dataset created: {dataset.name}")
        return redirect("dataset_detail", dataset_id=dataset.id)
    except Exception as exc:
        messages.error(request, f"Could not create dataset: {exc}")
        return redirect("dicom_import_detail", session_id=session.id)


@login_required
@require_POST
def run_l3_analysis_view(request, session_id):
    session = get_object_or_404(
        DicomImportSession,
        id=session_id,
        owner=request.user,
    )

    try:
        pipeline_run = start_l3_pipeline_for_import(session)
        messages.success(
            request,
            f"L3 analysis queued. Pipeline run: {pipeline_run.id}",
        )
        return redirect("pipelines")
    except Exception as exc:
        messages.error(request, f"Could not start L3 analysis: {exc}")
        return redirect("dicom_import_detail", session_id=session.id)


@login_required
@require_POST
def delete_import_view(request, session_id):
    session = get_object_or_404(
        DicomImportSession,
        id=session_id,
        owner=request.user,
    )

    try:
        delete_import_session(session)
        messages.success(request, "DICOM import deleted.")
        return redirect("dicom_imports")
    except Exception as exc:
        messages.error(request, f"Could not delete DICOM import: {exc}")
        return redirect("dicom_import_detail", session_id=session.id)
    

@login_required
@require_POST
def delete_all_imports_view(request):
    try:
        deleted_count = delete_all_import_sessions(request.user)
        messages.success(
            request,
            f"Deleted {deleted_count} DICOM import{'s' if deleted_count != 1 else ''}.",
        )
    except Exception as exc:
        messages.error(request, f"Could not delete all DICOM imports: {exc}")

    return redirect("dicom_imports")