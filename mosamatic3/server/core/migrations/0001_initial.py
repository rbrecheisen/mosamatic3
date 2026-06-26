# Generated migration scaffold
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('kind', models.CharField(choices=[('input','Input'),('output','Output')], db_index=True, default='input', max_length=20)),
                ('source_task_key', models.CharField(blank=True, db_index=True, max_length=100, null=True)),
                ('source_task_id', models.CharField(blank=True, db_index=True, max_length=100, null=True)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='datasets', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='DatasetFile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('relative_path', models.TextField()),
                ('size_bytes', models.BigIntegerField(default=0)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='core.dataset')),
            ],
            options={'ordering': ['relative_path']},
        ),
        migrations.CreateModel(
            name='FormSubmission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('text_value', models.TextField()),
                ('enabled', models.BooleanField(default=False)),
                ('choice', models.CharField(max_length=100)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='form_submissions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TaskParameters',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('task_key', models.CharField(db_index=True, max_length=100)),
                ('parameters', models.JSONField(default=dict)),
                ('is_valid', models.BooleanField(default=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('updated_at', models.DateTimeField(default=timezone.now)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_parameters', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TaskRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('task_key', models.CharField(db_index=True, max_length=100)),
                ('celery_task_id', models.CharField(db_index=True, max_length=100, unique=True)),
                ('status', models.CharField(db_index=True, default='queued', max_length=40)),
                ('cancel_requested', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('updated_at', models.DateTimeField(default=timezone.now)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_runs', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(model_name='dataset', constraint=models.UniqueConstraint(fields=('owner','name'), name='uq_dataset_owner_name')),
        migrations.AddConstraint(model_name='taskparameters', constraint=models.UniqueConstraint(fields=('owner','task_key'), name='uq_task_parameters_owner_task')),
    ]
