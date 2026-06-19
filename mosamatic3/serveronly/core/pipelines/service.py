from uuid import uuid4

from celery.result import AsyncResult
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from config.celery_app import app as celery_app
from core.models import Dataset, PipelineRun, PipelineStepRun
from core.tasking.registry import TASKS
from core.tasking.services import validate_task_parameters
from .configloader import load_pipeline_config, list_pipeline_configs


def get_pipeline_run_or_404(pipeline_run_id, user) -> PipelineRun:
    pipeline_run = PipelineRun.objects.filter(
        id=pipeline_run_id,
        owner=user,
    ).first()

    if pipeline_run is None:
        raise NotFound(f"Pipeline run not found: {pipeline_run_id}")

    return pipeline_run


def get_available_pipelines() -> list[dict]:
    return list_pipeline_configs()


def validate_pipeline_config(config: dict, user, initial_dataset: Dataset) -> dict:
    if "steps" not in config or not isinstance(config["steps"], list) or not config["steps"]:
        raise ValidationError("Pipeline config must contain a non-empty steps list.")

    seen_step_ids = set()

    for index, step in enumerate(config["steps"]):
        step_id = step.get("id")
        task_key = step.get("task_key")
        input_parameter = step.get("input_parameter")
        parameters = step.get("parameters") or {}

        if not step_id:
            raise ValidationError(f"Pipeline step {index} misses id.")

        if step_id in seen_step_ids:
            raise ValidationError(f"Duplicate pipeline step id: {step_id}")

        seen_step_ids.add(step_id)

        if task_key not in TASKS:
            raise ValidationError(f"Unknown task_key in pipeline step {step_id}: {task_key}")

        if not input_parameter:
            raise ValidationError(f"Pipeline step {step_id} misses input_parameter.")

        # Do not fully validate previous-step dataset references here,
        # because they do not exist yet. That happens during execution.
        if step.get("input_dataset") == "$initial_dataset":
            parameters[input_parameter] = str(initial_dataset.id)

            validate_task_parameters(
                task_key=task_key,
                parameters=parameters,
                user=user,
            )

    return config


def create_pipeline_run(
    *,
    user,
    config_key: str,
    initial_dataset_id,
    overrides: dict | None = None,
) -> PipelineRun:
    initial_dataset = Dataset.objects.filter(
        id=initial_dataset_id,
        owner=user,
    ).first()

    if initial_dataset is None:
        raise NotFound(f"Initial dataset not found: {initial_dataset_id}")

    config = load_pipeline_config(config_key)

    if overrides:
        config = apply_pipeline_overrides(config, overrides)

    validate_pipeline_config(
        config=config,
        user=user,
        initial_dataset=initial_dataset,
    )

    celery_task_id = str(uuid4())

    pipeline_run = PipelineRun.objects.create(
        owner=user,
        name=config.get("name", config_key),
        config=config,
        initial_dataset=initial_dataset,
        status=PipelineRun.STATUS_PENDING,
        celery_task_id=celery_task_id,
    )

    celery_app.send_task(
        "core.pipelines.tasks.run_pipeline",
        args=[str(pipeline_run.id)],
        task_id=celery_task_id,
        queue="pipeline",
    )

    return pipeline_run


def apply_pipeline_overrides(config: dict, overrides: dict) -> dict:
    """
    Simple override mechanism.

    Expected shape:

    {
      "steps": {
        "segment": {
          "parameters": {
            "model_files_dataset_id": "..."
          }
        }
      }
    }
    """

    config = dict(config)
    config["steps"] = [dict(step) for step in config["steps"]]

    step_overrides = overrides.get("steps") or {}

    for step in config["steps"]:
        step_id = step["id"]
        override = step_overrides.get(step_id) or {}

        if "parameters" in override:
            parameters = dict(step.get("parameters") or {})
            parameters.update(override["parameters"])
            step["parameters"] = parameters

    return config


def cancel_pipeline_run(pipeline_run_id, user) -> PipelineRun:
    pipeline_run = get_pipeline_run_or_404(pipeline_run_id, user)

    pipeline_run.is_cancel_requested = True

    if pipeline_run.status in [
        PipelineRun.STATUS_PENDING,
        PipelineRun.STATUS_RUNNING,
    ]:
        pipeline_run.status = PipelineRun.STATUS_CANCELED
        pipeline_run.finished_at = timezone.now()

    pipeline_run.save(
        update_fields=[
            "is_cancel_requested",
            "status",
            "finished_at",
        ]
    )

    running_step = pipeline_run.step_runs.filter(
        status=PipelineStepRun.STATUS_RUNNING,
    ).order_by("-started_at").first()

    if running_step and running_step.celery_task_id:
        result = AsyncResult(running_step.celery_task_id, app=celery_app)
        result.revoke(terminate=False)

    return pipeline_run


def get_pipeline_status(pipeline_run_id, user) -> dict:
    pipeline_run = get_pipeline_run_or_404(pipeline_run_id, user)

    return {
        "id": str(pipeline_run.id),
        "name": pipeline_run.name,
        "status": pipeline_run.status,
        "current_step_id": pipeline_run.current_step_id,
        "error_message": pipeline_run.error_message,
        "created_at": pipeline_run.created_at,
        "started_at": pipeline_run.started_at,
        "finished_at": pipeline_run.finished_at,
        "steps": [
            {
                "id": str(step.id),
                "step_id": step.step_id,
                "task_key": step.task_key,
                "status": step.status,
                "celery_task_id": step.celery_task_id,
                "input_dataset_id": str(step.input_dataset_id) if step.input_dataset_id else None,
                "output_dataset_id": str(step.output_dataset_id) if step.output_dataset_id else None,
                "error_message": step.error_message,
                "started_at": step.started_at,
                "finished_at": step.finished_at,
            }
            for step in pipeline_run.step_runs.all()
        ],
    }