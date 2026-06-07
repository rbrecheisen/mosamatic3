from django.urls import path
from . import api_views

urlpatterns = [
    path('', api_views.datasets),
    path('output-results', api_views.delete_output_results),
    path('<uuid:dataset_id>', api_views.dataset_detail),
    path('<uuid:dataset_id>/download', api_views.download_dataset),
]
