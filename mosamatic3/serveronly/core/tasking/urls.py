from django.urls import path
from . import views

urlpatterns = [
    path('tasks/', views.tasks_page, name='tasks'),
    path('tasks/<str:task_key>/', views.task_parameters_page, name='task_parameters'),
]
