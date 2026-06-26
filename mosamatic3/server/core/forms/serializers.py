from rest_framework import serializers
from ..models import FormSubmission

class FormSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormSubmission
        fields = ['id', 'text_value', 'enabled', 'choice', 'notes', 'created_at']
