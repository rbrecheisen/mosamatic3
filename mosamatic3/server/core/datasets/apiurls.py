from django.urls import path
from . import apiviews

urlpatterns = [
    path('', apiviews.datasets),
    path('input-datasets/', apiviews.delete_input_datasets),
    path('output-results/', apiviews.delete_output_results),
    path('<uuid:dataset_id>/', apiviews.dataset_detail),
    path('<uuid:dataset_id>/download/', apiviews.download_dataset),
]
