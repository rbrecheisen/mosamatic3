from django.urls import path
from . import apiviews

urlpatterns = [
    path('register/', apiviews.register),
    path('login/', apiviews.login),
    path('me/', apiviews.me),
]
