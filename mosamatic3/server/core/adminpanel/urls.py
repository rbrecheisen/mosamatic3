from django.urls import path
from . import views

urlpatterns = [
    path('admin-panel/', views.admin_panel_page, name='admin_panel'),
    path(
        'admin-panel/support-bundle/',
        views.download_support_bundle,
        name='download_support_bundle',
    ),
]