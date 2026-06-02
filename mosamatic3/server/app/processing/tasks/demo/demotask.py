import time
from typing import Any
from ...app import celery_app
from app.processing.tasks.demo.demo import run_task


@celery_app.task(bind=True, name="app.processing.tasks.demo.demotask")
def demotask(
  self, 
  seconds: int = 5, 
  single_dataset_id: str | None = None,
  text_value: str = "",
  checkbox_value: bool = False,
  slider_value: float = 50,
  dataset_ids: list[str] | None = None,
) -> dict[str, Any]:
  total_steps = max(1, int(seconds))
  for step in range(total_steps):
    self.update_state(
      state="PROGRESS",
      meta={
        "current": step + 1,
        "total": total_steps,
        "message": f"Processing step {step + 1} of {total_steps}",
        "single_dataset_id": single_dataset_id,
        "text_value": text_value,
        "checkbox_value": checkbox_value,
        "slider_value": slider_value,
        "dataset_ids": dataset_ids or [],
      },
    )
    run_task()
  return {
    "current": total_steps,
    "total": total_steps,
    "message": "Task completed",
    "single_dataset_id": single_dataset_id,
    "text_value": text_value,
    "checkbox_value": checkbox_value,
    "slider_value": slider_value,
    "dataset_ids": dataset_ids or [],
  }
