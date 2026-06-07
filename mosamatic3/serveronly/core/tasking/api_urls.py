from django.urls import path
from . import api_views

urlpatterns = [
    path('', api_views.tasks_list),
    path('<str:task_key>/schema', api_views.task_schema),
    path('<str:task_key>/parameters', api_views.task_parameters),
    path('<str:task_key>/run', api_views.task_run),
    path('<str:task_id>', api_views.task_status),
    path('<str:task_id>/cancel', api_views.task_cancel),
]
