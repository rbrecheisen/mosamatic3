import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from ..models import Dataset
from .registry import TASKS
from .services import get_saved_task_parameters


@login_required
def analysis_page(request):
    return render(request, 'tasking/analysis.html', {'tasks': TASKS.values()})


@login_required
def task_parameters_page(request, task_key):
    task = TASKS.get(task_key)
    if task is None:
        messages.error(request, f'Unknown task: {task_key}')
        return redirect('analysis')
    # datasets = Dataset.objects.filter(owner=request.user, kind='input').order_by('name')
    datasets = Dataset.objects.filter(owner=request.user).order_by('kind', 'name')
    saved = get_saved_task_parameters(task_key, request.user)
    schema = task.parameter_schema.model_json_schema()
    return render(request, 'tasking/task_parameters.html', {'task': task, 'schema_json': json.dumps(schema), 'saved_json': json.dumps(saved['parameters']), 'saved': saved, 'datasets': datasets})
