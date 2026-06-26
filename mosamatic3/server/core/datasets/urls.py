from django.urls import path
from . import views

urlpatterns = [
    path('data/', views.data_page, name='data'),
    path('data/<uuid:dataset_id>/', views.dataset_detail_page, name='dataset_detail'),
]
