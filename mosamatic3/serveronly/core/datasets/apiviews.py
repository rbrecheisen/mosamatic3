from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from ..models import Dataset
from .serializers import DatasetSerializer
from .services import create_dataset_for_user, create_dataset_zip_for_user, delete_dataset_and_files

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
