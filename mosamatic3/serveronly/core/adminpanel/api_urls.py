from django.urls import path
from . import api_views

urlpatterns = [
    path('summary', api_views.admin_summary),
    path('users', api_views.admin_users),
    path('datasets', api_views.admin_datasets),
    path('users/<int:user_id>/block', api_views.admin_block_user),
    path('users/<int:user_id>/unblock', api_views.admin_unblock_user),
    path('users/<int:user_id>', api_views.admin_delete_user),
]
