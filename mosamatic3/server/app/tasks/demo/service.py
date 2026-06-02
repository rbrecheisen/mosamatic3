import time
from typing import Any
from app.tasks.demo.schema import DemoTaskParameters


def run_demo_task(
  parameters: dict,
  user_id: str,
  celery_task: Any | None = None,
) -> dict:
  params = DemoTaskParameters.model_validate(parameters)
  total_iterations = params.integer_value

  if celery_task is not None:
    celery_task.update_state(
      state="PROGRESS",
      meta={
        "current": 0,
        "total": total_iterations,
        "message": "Starting demo task",
      },
    )

  print("Demo task")
  print(f"User ID: {user_id}")
  print(f"Text value: {params.text_value}")
  print(f"Integer value: {params.integer_value}")
  print(f"Float value: {params.float_value}")
  print(f"Slider value: {params.slider_value}")
  print(f"Processing mode: {params.processing_mode}")
  print(f"Enable debug output: {params.enable_debug_output}")
  print(f"Single dataset ID: {params.dataset_id}")
  for dataset_id in params.dataset_ids:
    print(f"Selected dataset ID: {dataset_id}")

  for iteration in range(total_iterations):
    current_iteration = iteration + 1
    message = f"Demo task iteration {current_iteration} of {total_iterations}"
    print(message)

    # Update task status for this iteration
    if celery_task is not None:
      celery_task.update_state(
        state="PROGRESS",
        meta={
          "current": current_iteration,
          "total": total_iterations,
          "message": message,
        },
      )
    time.sleep(1)

  return {
    "current": total_iterations,
    "total": total_iterations,
    "message": "Demo task completed",
    "parameters": params.model_dump(mode="json"),
  }