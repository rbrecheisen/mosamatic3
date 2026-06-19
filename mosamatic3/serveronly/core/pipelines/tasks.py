from uuid import uuid4

from celery.exceptions import Ignore
from django.utils import timezone

from config.celery_app import app
from core.models import Dataset, PipelineRun, PipelineStepRun
from core.tasking.registry import TASKS
from core.tasking.services import validate_task_parameters
from core.tasking.taskrunservice import create_task_run
from .resolver import resolve_dataset_reference, extract_first_output_dataset_id


@app.task(bind=True, name="core.pipelines.tasks.run_pipeline")
def run_pipeline(self, pipeline_run_id: str) -> dict:
    pipeline_run = PipelineRun.objects.get(id=pipeline_run_id)

    pipeline_run.status = PipelineRun.STATUS_RUNNING
    pipeline_run.started_at = timezone.now()
    pipeline_run.save(update_fields=["status", "started_at"])

    context = {
        "initial_dataset": str(pipeline_run.initial_dataset_id),
        "steps": {},
    }

    try:
        for order, step_config in enumerate(pipeline_run.config["steps"]):
            pipeline_run.refresh_from_db()

            if pipeline_run.is_cancel_requested:
                pipeline_run.status = PipelineRun.STATUS_CANCELED
                pipeline_run.finished_at = timezone.now()
                pipeline_run.save(update_fields=["status", "finished_at"])
                return {"status": "CANCELED"}

            step_id = step_config["id"]
            task_key = step_config["task_key"]
            input_parameter = step_config["input_parameter"]

            task_definition = TASKS[task_key]

            input_dataset_id = resolve_dataset_reference(
                step_config["input_dataset"],
                context,
            )

            input_dataset = Dataset.objects.get(
                id=input_dataset_id,
                owner=pipeline_run.owner,
            )

            parameters = dict(step_config.get("parameters") or {})
            parameters[input_parameter] = str(input_dataset.id)

            parameters = validate_task_parameters(
                task_key=task_key,
                parameters=parameters,
                user=pipeline_run.owner,
            )

            step_run = PipelineStepRun.objects.create(
                pipeline_run=pipeline_run,
                step_id=step_id,
                task_key=task_key,
                status=PipelineStepRun.STATUS_RUNNING,
                input_dataset=input_dataset,
                parameters=parameters,
                order=order,
                started_at=timezone.now(),
            )

            pipeline_run.current_step_id = step_id
            pipeline_run.save(update_fields=["current_step_id"])

            celery_task_id = str(uuid4())

            create_task_run(
                owner=pipeline_run.owner,
                task_key=task_key,
                celery_task_id=celery_task_id,
            )

            step_run.celery_task_id = celery_task_id
            step_run.save(update_fields=["celery_task_id"])

            async_result = app.send_task(
                task_definition.celery_task_name,
                args=[parameters, str(pipeline_run.owner_id)],
                task_id=celery_task_id,
                queue="tasks",
            )

            result = async_result.get(
                propagate=False,
                disable_sync_subtasks=False,
            )

            pipeline_run.refresh_from_db()

            if pipeline_run.is_cancel_requested:
                step_run.status = PipelineStepRun.STATUS_CANCELED
                step_run.finished_at = timezone.now()
                step_run.save(update_fields=["status", "finished_at"])

                pipeline_run.status = PipelineRun.STATUS_CANCELED
                pipeline_run.finished_at = timezone.now()
                pipeline_run.save(update_fields=["status", "finished_at"])

                return {"status": "CANCELED"}

            if async_result.state != "SUCCESS":
                step_run.status = PipelineStepRun.STATUS_FAILURE
                step_run.error_message = str(result)
                step_run.finished_at = timezone.now()
                step_run.save(update_fields=["status", "error_message", "finished_at"])

                pipeline_run.status = PipelineRun.STATUS_FAILURE
                pipeline_run.error_message = f"Step '{step_id}' failed: {result}"
                pipeline_run.finished_at = timezone.now()
                pipeline_run.save(
                    update_fields=[
                        "status",
                        "error_message",
                        "finished_at",
                    ]
                )

                return {
                    "status": "FAILURE",
                    "failed_step": step_id,
                    "error": str(result),
                }

            output_dataset_id = extract_first_output_dataset_id(result)

            output_dataset = Dataset.objects.get(
                id=output_dataset_id,
                owner=pipeline_run.owner,
            )

            step_run.status = PipelineStepRun.STATUS_SUCCESS
            step_run.output_dataset = output_dataset
            step_run.finished_at = timezone.now()
            step_run.save(update_fields=["status", "output_dataset", "finished_at"])

            context["steps"][step_id] = {
                "output_dataset": str(output_dataset.id),
            }

        pipeline_run.status = PipelineRun.STATUS_SUCCESS
        pipeline_run.current_step_id = None
        pipeline_run.finished_at = timezone.now()
        pipeline_run.save(update_fields=["status", "current_step_id", "finished_at"])

        return {
            "status": "SUCCESS",
            "pipeline_run_id": str(pipeline_run.id),
            "steps": context["steps"],
        }

    except Ignore:
        pipeline_run.status = PipelineRun.STATUS_CANCELED
        pipeline_run.finished_at = timezone.now()
        pipeline_run.save(update_fields=["status", "finished_at"])
        raise

    except Exception as exc:
        pipeline_run.status = PipelineRun.STATUS_FAILURE
        pipeline_run.error_message = str(exc)
        pipeline_run.finished_at = timezone.now()
        pipeline_run.save(update_fields=["status", "error_message", "finished_at"])
        raise