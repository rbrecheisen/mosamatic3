from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Dataset, DatasetFile, FormSubmission, TaskParameters

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

class DatasetFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatasetFile
        fields = ['id', 'relative_path', 'size_bytes', 'created_at']

class DatasetSerializer(serializers.ModelSerializer):
    files = DatasetFileSerializer(many=True, read_only=True)
    file_count = serializers.SerializerMethodField()
    total_size_bytes = serializers.SerializerMethodField()

    class Meta:
        model = Dataset
        fields = ['id', 'name', 'kind', 'source_task_key', 'source_task_id', 'created_at', 'file_count', 'total_size_bytes', 'files']

    def get_file_count(self, obj):
        return obj.files.count()

    def get_total_size_bytes(self, obj):
        return sum(obj.files.values_list('size_bytes', flat=True))

class AdminDatasetSerializer(DatasetSerializer):
    owner_id = serializers.IntegerField(source='owner.id')

    class Meta(DatasetSerializer.Meta):
        fields = DatasetSerializer.Meta.fields + ['owner_id']

class FormSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormSubmission
        fields = ['id', 'text_value', 'enabled', 'choice', 'notes', 'created_at']

class TaskParametersSerializer(serializers.ModelSerializer):
    exists = serializers.SerializerMethodField()

    class Meta:
        model = TaskParameters
        fields = ['task_key', 'parameters', 'is_valid', 'error_message', 'exists', 'updated_at']

    def get_exists(self, obj):
        return True
