import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Dataset(models.Model):
    KIND_CHOICES = [('input', 'Input'), ('output', 'Output')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='datasets')
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='input', db_index=True)
    source_task_key = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    source_task_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'name'], name='uq_dataset_owner_name')]
        ordering = ['-created_at']

    @property
    def file_count(self):
        return self.files.count()

    @property
    def total_size_bytes(self):
        return sum(self.files.values_list('size_bytes', flat=True))

    def __str__(self):
        return self.name

class DatasetFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='files')
    relative_path = models.TextField()
    size_bytes = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['relative_path']

class TaskParameters(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_parameters')
    task_key = models.CharField(max_length=100, db_index=True)
    parameters = models.JSONField(default=dict)
    is_valid = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'task_key'], name='uq_task_parameters_owner_task')]

class TaskRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_runs')
    task_key = models.CharField(max_length=100, db_index=True)
    celery_task_id = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=40, default='queued', db_index=True)
    cancel_requested = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

class FormSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='form_submissions')
    text_value = models.TextField()
    enabled = models.BooleanField(default=False)
    choice = models.CharField(max_length=100)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
