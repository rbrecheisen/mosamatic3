from django.urls import path
from . import views

urlpatterns = [
    path('visual-analytics/', views.visual_analytics, name='visual_analytics'),
]
