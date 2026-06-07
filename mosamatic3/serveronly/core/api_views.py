from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Count
from django.http import HttpResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from .auth import create_access_token
from .dataset_service import create_dataset_for_user, create_dataset_zip_for_user, delete_dataset_and_files
from .models import Dataset, DatasetFile, FormSubmission
from .serializers import AdminDatasetSerializer, DatasetSerializer, FormSubmissionSerializer, UserReadSerializer
from .task_registry import TASKS
from .task_service import cancel_task_by_id, get_celery_task_status, get_saved_task_parameters, save_task_parameters, start_task_by_key

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    return Response({'status': 'ok'})

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request):
    email = (request.data.get('email') or '').strip()
    password = request.data.get('password') or ''
    if not email or not password:
        raise ValidationError('Email and password are required')
    if User.objects.filter(username=email).exists():
        raise ValidationError('Email already registered')
    user = User.objects.create_user(username=email, password=password, email=email)
    return Response(UserReadSerializer(user).data, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get('username') or request.POST.get('username')
    password = request.data.get('password') or request.POST.get('password')
    user = authenticate(username=username, password=password)
    if user is None:
        return Response({'detail': 'Incorrect email or password'}, status=status.HTTP_401_UNAUTHORIZED)
    return Response({'access_token': create_access_token(user.username), 'token_type': 'bearer'})

@api_view(['GET'])
def me(request):
    return Response(UserReadSerializer(request.user).data)

@api_view(['GET', 'POST'])
def datasets(request):
    if request.method == 'GET':
        qs = Dataset.objects.filter(owner=request.user).prefetch_related('files').order_by('-created_at')
        return Response(DatasetSerializer(qs, many=True).data)
    dataset = create_dataset_for_user(request.data.get('name') or '', request.FILES.getlist('files'), request.user)
    return Response(DatasetSerializer(dataset).data, status=status.HTTP_201_CREATED)

@api_view(['GET', 'DELETE'])
def dataset_detail(request, dataset_id):
    try:
        dataset = Dataset.objects.prefetch_related('files').get(id=dataset_id, owner=request.user)
    except Dataset.DoesNotExist:
        raise NotFound('Dataset not found')
    if request.method == 'DELETE':
        delete_dataset_and_files(dataset)
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(DatasetSerializer(dataset).data)

@api_view(['GET'])
def download_dataset(request, dataset_id):
    filename, content = create_dataset_zip_for_user(dataset_id, request.user)
    response = HttpResponse(content, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@api_view(['DELETE'])
def delete_output_results(request):
    for dataset in Dataset.objects.filter(owner=request.user, kind='output'):
        delete_dataset_and_files(dataset)
    return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
def forms(request):
    if request.method == 'GET':
        qs = FormSubmission.objects.filter(owner=request.user).order_by('-created_at')
        return Response(FormSubmissionSerializer(qs, many=True).data)
    serializer = FormSubmissionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    submission = serializer.save(owner=request.user)
    return Response(FormSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)

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

def require_admin(user):
    if not user.is_staff:
        raise PermissionDenied('Admin access required')

@api_view(['GET'])
def admin_summary(request):
    require_admin(request.user)
    return Response({'user_count': User.objects.count(), 'dataset_count': Dataset.objects.count(), 'dataset_file_count': DatasetFile.objects.count()})

@api_view(['GET'])
def admin_users(request):
    require_admin(request.user)
    return Response(UserReadSerializer(User.objects.order_by('username'), many=True).data)

@api_view(['GET'])
def admin_datasets(request):
    require_admin(request.user)
    return Response(AdminDatasetSerializer(Dataset.objects.prefetch_related('files').all(), many=True).data)

@api_view(['PATCH', 'POST'])
def admin_block_user(request, user_id):
    require_admin(request.user)
    target = User.objects.get(id=user_id)
    if target.id == request.user.id:
        raise ValidationError('You cannot block your own admin account.')
    target.is_active = False
    target.save(update_fields=['is_active'])
    return Response(UserReadSerializer(target).data)

@api_view(['PATCH', 'POST'])
def admin_unblock_user(request, user_id):
    require_admin(request.user)
    target = User.objects.get(id=user_id)
    target.is_active = True
    target.save(update_fields=['is_active'])
    return Response(UserReadSerializer(target).data)

@api_view(['DELETE'])
def admin_delete_user(request, user_id):
    require_admin(request.user)
    target = User.objects.get(id=user_id)
    if target.id == request.user.id:
        raise ValidationError('You cannot delete your own admin account.')
    target.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
