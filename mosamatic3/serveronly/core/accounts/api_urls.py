from django.urls import path
from . import api_views

urlpatterns = [
    path('register', api_views.register),
    path('login', api_views.login),
    path('me', api_views.me),
]
