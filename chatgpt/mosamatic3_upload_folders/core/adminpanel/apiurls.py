from django.urls import path
from . import apiviews

urlpatterns = [
    path('summary', apiviews.admin_summary),
    path('users', apiviews.admin_users),
    path('datasets', apiviews.admin_datasets),
    path('users/<int:user_id>/block', apiviews.admin_block_user),
    path('users/<int:user_id>/unblock', apiviews.admin_unblock_user),
    path('users/<int:user_id>', apiviews.admin_delete_user),
]
