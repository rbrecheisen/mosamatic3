from django.urls import path
from . import apiviews

urlpatterns = [
    path('', apiviews.forms),
]
