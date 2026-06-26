from typing import Any
from uuid import uuid4

from celery.result import AsyncResult
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from config.celery_app import app as celery_app

from ..models import Dataset, TaskParameters
from .registry import TASKS
from .taskrunservice import create_task_run, request_task_cancel


def get_task_definition_or_404(task_key: str):
    task = TASKS.get(task_key)
    if task is None:
        raise NotFound(f'Unknown task: {task_key}')
    return task


def iter_dataset_reference_values(parameter_model, parameters: dict[str, Any]):
    for field_name, field in parameter_model.model_fields.items():
        extra = field.json_schema_extra or {}

        if not extra.get('dataset_reference'):
            continue

        value = parameters.get(field_name)

        if value in (None, ''):
            continue

        if isinstance(value, list):
            for item in value:
                if item not in (None, ''):
                    yield field_name, item
        else:
            yield field_name, value


def validate_dataset_references(
    task_key: str,
    parameters: dict[str, Any],
    user,
) -> None:
    task_definition = get_task_definition_or_404(task_key)
    parameter_model = task_definition.parameter_schema

    for field_name, dataset_id in iter_dataset_reference_values(parameter_model, parameters):
        if not Dataset.objects.filter(owner=user, id=dataset_id).exists():
            raise NotFound(
                f'Dataset referenced by parameter "{field_name}" does not exist: {dataset_id}'
            )


def validate_task_parameters(
    task_key: str,
    parameters: dict[str, Any],
    user,
) -> dict[str, Any]:
    task = get_task_definition_or_404(task_key)

    try:
        validated = task.parameter_schema.model_validate(parameters).model_dump(mode='json')
    except Exception as exc:
        errors = exc.errors() if hasattr(exc, 'errors') else str(exc)
        raise ValidationError(errors) from exc

    validate_dataset_references(task_key, validated, user)

    return validated


def get_saved_task_parameters(task_key: str, user):
    get_task_definition_or_404(task_key)

    saved = TaskParameters.objects.filter(
        owner=user,
        task_key=task_key,
    ).first()

    if saved is None:
        return {
            'task_key': task_key,
            'parameters': {},
            'is_valid': False,
            'error_message': None,
            'exists': False,
            'updated_at': None,
        }

    return {
        'task_key': saved.task_key,
        'parameters': saved.parameters,
        'is_valid': saved.is_valid,
        'error_message': saved.error_message,
        'exists': True,
        'updated_at': saved.updated_at,
    }


def save_task_parameters(task_key: str, payload: dict, user):
    if payload.get('task_key') != task_key:
        raise ValidationError('Task key in URL and request body do not match.')

    validated = validate_task_parameters(
        task_key,
        payload.get('parameters') or {},
        user,
    )

    TaskParameters.objects.update_or_create(
        owner=user,
        task_key=task_key,
        defaults={
            'parameters': validated,
            'is_valid': True,
            'error_message': None,
            'updated_at': timezone.now(),
        },
    )

    return get_saved_task_parameters(task_key, user)


def start_task_by_key(task_key: str, user) -> dict[str, str]:
    task = get_task_definition_or_404(task_key)

    saved = TaskParameters.objects.filter(
        owner=user,
        task_key=task_key,
        is_valid=True,
    ).first()

    if saved is None:
        raise ValidationError(
            'Valid task parameters must be submitted before running this task.'
        )

    parameters = validate_task_parameters(task_key, saved.parameters, user)

    celery_task_id = str(uuid4())

    create_task_run(
        owner=user,
        task_key=task_key,
        celery_task_id=celery_task_id,
    )

    celery_app.send_task(
        task.celery_task_name,
        args=[parameters, str(user.id)],
        task_id=celery_task_id,
        queue='tasks',
    )

    return {
        'task_id': celery_task_id,
        'status': 'queued',
    }


def cancel_task_by_id(task_id: str, user) -> dict[str, object]:
    task_run = request_task_cancel(task_id, user)

    if task_run is None:
        raise NotFound(f'Task run not found: {task_id}')

    result = AsyncResult(task_id, app=celery_app)
    result.revoke(terminate=False)

    return {
        'task_id': task_id,
        'status': 'cancel_requested',
        'message': 'Cancel requested',
    }


def get_celery_task_status(task_id: str) -> dict[str, object]:
    result = AsyncResult(task_id, app=celery_app)

    response = {
        'task_id': task_id,
        'state': result.state,
    }

    if result.state == 'PENDING':
        response['message'] = 'Task is pending or unknown'

    elif result.state == 'REVOKED':
        response['message'] = 'Task was cancelled'

    elif result.state == 'FAILURE':
        response['message'] = str(result.info)

    elif isinstance(result.info, dict):
        response.update(result.info)

    elif result.ready():
        response['result'] = result.result

    return response