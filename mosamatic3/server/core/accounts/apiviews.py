from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from .auth import create_access_token
from .serializers import UserReadSerializer
from core.datasets.system import sync_builtin_model_files_dataset_for_user

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
    sync_builtin_model_files_dataset_for_user(user)
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
