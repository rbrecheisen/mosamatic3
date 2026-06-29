from django.urls import path
from . import apiviews

urlpatterns = [
    path("", apiviews.pipeline_list),
    path("run/", apiviews.pipeline_run),
    path("delete-all/", apiviews.pipeline_delete_all),
    path("<uuid:pipeline_run_id>/", apiviews.pipeline_status),
    path("<uuid:pipeline_run_id>/cancel/", apiviews.pipeline_cancel),
    path("<uuid:pipeline_run_id>/delete/", apiviews.pipeline_delete),
]