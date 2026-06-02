from typing import Any

from app.tasks.demo.schema import DemoTaskParameters


def run_demo_task(
  parameters: dict,
  user_id: str,
  celery_task: Any | None = None,
) -> dict:
  params = DemoTaskParameters.model_validate(parameters)

  if celery_task is not None:
    celery_task.update_state(
      state="PROGRESS",
      meta={
        "current": 0,
        "total": 1,
        "message": "Starting demo task",
      },
    )

  print("Demo task")
  print("User ID:", user_id)
  print("Text value:", params.text_value)
  print("Integer value:", params.integer_value)
  print("Float value:", params.float_value)
  print("Slider value:", params.slider_value)
  print("Processing mode:", params.processing_mode)
  print("Enable debug output:", params.enable_debug_output)
  print("Single dataset ID:", params.dataset_id)

  for dataset_id in params.dataset_ids:
    print("Selected dataset ID:", dataset_id)

  if celery_task is not None:
    celery_task.update_state(
      state="PROGRESS",
      meta={
        "current": 1,
        "total": 1,
        "message": "Finished demo task",
      },
    )

  return {
    "current": 1,
    "total": 1,
    "message": "Demo task completed",
    "parameters": params.model_dump(mode="json"),
  }