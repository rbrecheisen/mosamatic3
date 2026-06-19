from django.urls import path
from . import views

urlpatterns = [
    path("pipelines/", views.pipelines, name="pipelines"),
]