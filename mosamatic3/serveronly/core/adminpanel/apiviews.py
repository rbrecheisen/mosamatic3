from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from ..models import Dataset, DatasetFile
from ..accounts.serializers import UserReadSerializer
from ..datasets.serializers import AdminDatasetSerializer

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
