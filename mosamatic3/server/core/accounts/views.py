from django.contrib import messages
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from core.datasets.system import sync_builtin_model_files_dataset_for_user


def login_page(request):
    if request.method == 'POST':
        username = request.POST.get('username') or ''
        password = request.POST.get('password') or ''
        user = authenticate(request, username=username, password=password)
        if user is not None:
            django_login(request, user)
            return redirect('home')
        messages.error(request, 'Incorrect username or password')
    return render(request, 'accounts/login.html')

def logout_page(request):
    django_logout(request)
    return redirect('login')

def register_page(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password') or ''
        if not email or not password:
            messages.error(request, 'Email and password are required')
        elif User.objects.filter(username=email).exists():
            messages.error(request, 'Email already registered')
        else:
            user = User.objects.create_user(username=email, email=email, password=password)
            sync_builtin_model_files_dataset_for_user(user)
            django_login(request, user)
            return redirect('home')
    return render(request, 'accounts/register.html')
