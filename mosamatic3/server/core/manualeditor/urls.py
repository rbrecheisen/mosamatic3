from django.urls import path
from . import views

urlpatterns = [
    path("manual-editor/", views.manual_editor_page, name="manual_editor"),
]