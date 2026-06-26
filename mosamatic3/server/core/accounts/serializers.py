from django.contrib.auth.models import User
from rest_framework import serializers

class UserReadSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source='username')
    is_admin = serializers.BooleanField(source='is_staff')
    created_at = serializers.DateTimeField(source='date_joined')

    class Meta:
        model = User
        fields = ['id', 'email', 'is_active', 'is_admin', 'created_at']

class UserCreateSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)
