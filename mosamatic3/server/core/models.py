import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Dataset(models.Model):
    KIND_INPUT = 'input'
    KIND_OUTPUT = 'output'
    KIND_CHOICES = [('input', 'Input'), ('output', 'Output')]
    STATUS_CHOICES = [
        ('ready', 'Ready'),
        ('in_progress', 'In progress'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
        ('done', 'Done'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='datasets')
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='input', db_index=True)
    source_task_key = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    source_task_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='ready',
        db_index=True,
    )
    source_dataset = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_datasets',
    )
    parameter_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
    )
    created_at = models.DateTimeField(default=timezone.now)
    is_system = models.BooleanField(
        default=False,
        db_index=True,
        help_text='System-managed dataset that should not be deleted by users.',
    )

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

class PipelineRun(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILURE = "FAILURE"
    STATUS_CANCELED = "CANCELED"

    STATUS_CHOICES = [
        (STATUS_PENDING, STATUS_PENDING),
        (STATUS_RUNNING, STATUS_RUNNING),
        (STATUS_SUCCESS, STATUS_SUCCESS),
        (STATUS_FAILURE, STATUS_FAILURE),
        (STATUS_CANCELED, STATUS_CANCELED),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pipeline_runs",
    )

    name = models.CharField(max_length=255)
    config = models.JSONField()

    initial_dataset = models.ForeignKey(
        "Dataset",
        on_delete=models.SET_NULL,
        related_name="pipeline_runs_as_initial_input",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    current_step_id = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True)
    is_cancel_requested = models.BooleanField(default=False, db_index=True)

    celery_task_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.status})"


class PipelineStepRun(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILURE = "FAILURE"
    STATUS_CANCELED = "CANCELED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    pipeline_run = models.ForeignKey(
        PipelineRun,
        on_delete=models.CASCADE,
        related_name="step_runs",
    )

    step_id = models.CharField(max_length=255)
    task_key = models.CharField(max_length=100, db_index=True)

    status = models.CharField(max_length=32, default=STATUS_PENDING, db_index=True)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    input_dataset = models.ForeignKey(
        Dataset,
        on_delete=models.SET_NULL,
        related_name="pipeline_step_inputs",
        null=True,
        blank=True,
    )

    output_dataset = models.ForeignKey(
        Dataset,
        on_delete=models.SET_NULL,
        related_name="pipeline_step_outputs",
        null=True,
        blank=True,
    )

    parameters = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)

    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline_run", "step_id"],
                name="uq_pipeline_step_id_per_run",
            )
        ]

    def __str__(self):
        return f"{self.pipeline_run.name}: {self.step_id} ({self.status})"

class FormSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='form_submissions')
    text_value = models.TextField()
    enabled = models.BooleanField(default=False)
    choice = models.CharField(max_length=100)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
