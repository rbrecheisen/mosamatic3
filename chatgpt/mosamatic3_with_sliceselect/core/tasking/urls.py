from django.urls import path
from . import views

urlpatterns = [
    path('analysis/', views.analysis_page, name='analysis'),
    path('analysis/<str:task_key>/', views.task_parameters_page, name='task_parameters'),
]
