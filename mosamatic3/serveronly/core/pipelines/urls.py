from django.urls import path
from . import views

urlpatterns = [
    path("pipelines/", views.pipelines, name="pipelines"),
    path("pipelines/<str:config_key>/", views.pipeline_detail, name="pipeline_detail"),
]