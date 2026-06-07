from django.contrib import admin
from django.urls import include, path
from core import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_page, name='login'),
    path('logout/', views.logout_page, name='logout'),
    path('register/', views.register_page, name='register'),
    path('data/', views.data_page, name='data'),
    path('data/<uuid:dataset_id>/', views.dataset_detail_page, name='dataset_detail'),
    path('analysis/', views.analysis_page, name='analysis'),
    path('analysis/<str:task_key>/', views.task_parameters_page, name='task_parameters'),
    path('admin-panel/', views.admin_panel_page, name='admin_panel'),
    path('api/', include('core.api_urls')),
    path('admin/', admin.site.urls),
]
