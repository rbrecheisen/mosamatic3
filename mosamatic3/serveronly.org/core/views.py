import json
from django.contrib import messages
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from .models import Dataset
from .task_registry import TASKS
from .task_service import get_saved_task_parameters

@login_required
def home(request):
    return render(request, 'home.html')

def login_page(request):
    if request.method == 'POST':
        username = request.POST.get('username') or ''
        password = request.POST.get('password') or ''
        user = authenticate(request, username=username, password=password)
        if user is not None:
            django_login(request, user)
            return redirect('home')
        messages.error(request, 'Incorrect username or password')
    return render(request, 'login.html')

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
            django_login(request, user)
            return redirect('home')
    return render(request, 'register.html')

@login_required
def data_page(request):
    datasets = Dataset.objects.filter(owner=request.user).prefetch_related('files').order_by('-created_at')
    input_datasets = [d for d in datasets if d.kind != 'output']
    output_datasets = [d for d in datasets if d.kind == 'output']
    return render(request, 'data.html', {'input_datasets': input_datasets, 'output_datasets': output_datasets})

@login_required
def dataset_detail_page(request, dataset_id):
    dataset = get_object_or_404(Dataset.objects.prefetch_related('files'), id=dataset_id, owner=request.user)
    return render(request, 'dataset_detail.html', {'dataset': dataset})

@login_required
def analysis_page(request):
    return render(request, 'analysis.html', {'tasks': TASKS.values()})

@login_required
def task_parameters_page(request, task_key):
    task = TASKS.get(task_key)
    if task is None:
        messages.error(request, f'Unknown task: {task_key}')
        return redirect('analysis')
    datasets = Dataset.objects.filter(owner=request.user, kind='input').order_by('name')
    saved = get_saved_task_parameters(task_key, request.user)
    schema = task.parameter_schema.model_json_schema()
    return render(request, 'task_parameters.html', {'task': task, 'schema_json': json.dumps(schema), 'saved_json': json.dumps(saved['parameters']), 'saved': saved, 'datasets': datasets})

@login_required
def admin_panel_page(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access required')
        return redirect('home')
    return render(request, 'admin_panel.html', {'users': User.objects.order_by('username'), 'datasets': Dataset.objects.all().prefetch_related('files')})
