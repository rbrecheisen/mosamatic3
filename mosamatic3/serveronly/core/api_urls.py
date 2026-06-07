from django.urls import path
from . import api_views

urlpatterns = [
    path('health', api_views.health),
    path('auth/register', api_views.register),
    path('auth/login', api_views.login),
    path('auth/me', api_views.me),
    path('datasets', api_views.datasets),
    path('datasets/output-results', api_views.delete_output_results),
    path('datasets/<uuid:dataset_id>', api_views.dataset_detail),
    path('datasets/<uuid:dataset_id>/download', api_views.download_dataset),
    path('forms', api_views.forms),
    path('tasks', api_views.tasks_list),
    path('tasks/<str:task_key>/schema', api_views.task_schema),
    path('tasks/<str:task_key>/parameters', api_views.task_parameters),
    path('tasks/<str:task_key>/run', api_views.task_run),
    path('tasks/<str:task_id>', api_views.task_status),
    path('tasks/<str:task_id>/cancel', api_views.task_cancel),
    path('admin/summary', api_views.admin_summary),
    path('admin/users', api_views.admin_users),
    path('admin/datasets', api_views.admin_datasets),
    path('admin/users/<int:user_id>/block', api_views.admin_block_user),
    path('admin/users/<int:user_id>/unblock', api_views.admin_unblock_user),
    path('admin/users/<int:user_id>', api_views.admin_delete_user),
]
