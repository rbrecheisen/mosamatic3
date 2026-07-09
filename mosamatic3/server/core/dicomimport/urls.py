from django.urls import path
from . import views

urlpatterns = [
    path("dicom-imports/", views.dicom_imports_page, name="dicom_imports"),
    path(
        "dicom-imports/delete-all/",
        views.delete_all_imports_view,
        name="dicom_import_delete_all",
    ),
    path(
        "dicom-imports/<uuid:session_id>/",
        views.dicom_import_detail_page,
        name="dicom_import_detail",
    ),
    path(
        "dicom-imports/<uuid:session_id>/create-dataset/",
        views.create_dataset_view,
        name="dicom_import_create_dataset",
    ),
    path(
        "dicom-imports/<uuid:session_id>/run-l3-analysis/",
        views.run_l3_analysis_view,
        name="dicom_import_run_l3_analysis",
    ),
    path(
        "dicom-imports/<uuid:session_id>/delete/",
        views.delete_import_view,
        name="dicom_import_delete",
    ),
]