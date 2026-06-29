from django.urls import path
from . import apiviews

urlpatterns = [
    path('', apiviews.tasks_list),
    path('<str:task_key>/schema/', apiviews.task_schema),
    path('<str:task_key>/parameters/', apiviews.task_parameters),
    path('<str:task_key>/run/', apiviews.task_run),
    path('<str:task_id>/', apiviews.task_status),
    path('<str:task_id>/cancel/', apiviews.task_cancel),
]
