from rest_framework import serializers
from ..models import Dataset, DatasetFile

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
