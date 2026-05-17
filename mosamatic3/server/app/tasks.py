import time
from typing import Any
from .processing import celery_app


@celery_app.task(bind=True, name="app.tasks.demo_background_task")
def demo_background_task(self, seconds: int = 5) -> dict[str, Any]:
    """Small example task to verify that FastAPI can enqueue work in Celery.

    Replace this with real Mosamatic jobs later, e.g. DICOM conversion,
    segmentation, scoring, report generation, etc.
    """
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
        time.sleep(1)
    return {
        "current": total_steps,
        "total": total_steps,
        "message": "Task completed",
    }
