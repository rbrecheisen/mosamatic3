from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from .registry import TASKS
from .services import cancel_task_by_id, get_celery_task_status, get_saved_task_parameters, save_task_parameters, start_task_by_key

@api_view(['GET'])
def tasks_list(request):
    return Response([{'id': t.key, 'name': t.name, 'description': t.description} for t in TASKS.values()])

@api_view(['GET'])
def task_schema(request, task_key):
    task = TASKS.get(task_key)
    if task is None:
        raise NotFound(f'Unknown task: {task_key}')
    return Response({'id': task.key, 'name': task.name, 'description': task.description, 'schema': task.parameter_schema.model_json_schema()})

@api_view(['GET', 'POST'])
def task_parameters(request, task_key):
    if request.method == 'GET':
        return Response(get_saved_task_parameters(task_key, request.user))
    return Response(save_task_parameters(task_key, request.data, request.user))

@api_view(['POST'])
def task_run(request, task_key):
    return Response(start_task_by_key(task_key, request.user), status=status.HTTP_202_ACCEPTED)

@api_view(['GET'])
def task_status(request, task_id):
    return Response(get_celery_task_status(task_id))

@api_view(['POST'])
def task_cancel(request, task_id):
    return Response(cancel_task_by_id(task_id, request.user), status=status.HTTP_202_ACCEPTED)
