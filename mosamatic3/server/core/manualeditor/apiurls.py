from django.urls import path

from . import apiviews


urlpatterns = [
    path("datasets", apiviews.manual_editor_datasets),
    path("datasets/<uuid:dataset_id>/correction-datasets", apiviews.manual_editor_correction_datasets),
    path("datasets/<uuid:dataset_id>/cases", apiviews.manual_editor_cases),
    path("files/<uuid:file_id>/image", apiviews.manual_editor_image),
    path("files/<uuid:file_id>/segmentation", apiviews.manual_editor_segmentation),
    path("files/<uuid:file_id>/save-correction", apiviews.manual_editor_save_correction),
]