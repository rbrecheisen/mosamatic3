from rest_framework import serializers
from ..models import TaskParameters

class TaskParametersSerializer(serializers.ModelSerializer):
    exists = serializers.SerializerMethodField()

    class Meta:
        model = TaskParameters
        fields = ['task_key', 'parameters', 'is_valid', 'error_message', 'exists', 'updated_at']

    def get_exists(self, obj):
        return True
