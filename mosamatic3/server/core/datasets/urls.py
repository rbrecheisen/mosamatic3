from django.urls import path
from . import views

urlpatterns = [
    path('data/', views.data_page, name='data'),
    path('data/<uuid:dataset_id>/', views.dataset_detail_page, name='dataset_detail'),
    path(
        'data/<uuid:dataset_id>/files/<uuid:file_id>/',
        views.dataset_detail_page,
        name='dataset_file_detail',
    ),
    path(
        'data/<uuid:dataset_id>/files/<uuid:file_id>/raw/',
        views.dataset_file_raw,
        name='dataset_file_raw',
    ),
]