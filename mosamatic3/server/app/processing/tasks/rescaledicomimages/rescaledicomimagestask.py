import time
from typing import Any
from ...app import celery_app
from app.processing.tasks.rescaledicomimages.rescaledicomimage import run_task


@celery_app.task(bind=True, name="app.processing.tasks.rescaledicomimages.rescaledicomimagestask")
def rescaledicomimagestask(self, seconds: int = 5) -> dict[str, Any]:
  total_steps = max(1, int(seconds))
  for step in range(total_steps):
    self.update_state(
      state="PROGRESS",
      meta={
        "current": step + 1,
        "total": total_steps,
        "message": f"Processing step {step + 1} of {total_steps}",
      },
    )
    run_task()
  return {
    "current": total_steps,
    "total": total_steps,
    "message": "Task completed",
  }
