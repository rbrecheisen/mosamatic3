import time
from typing import Any
from ...app import celery_app


@celery_app.task(bind=True, name="app.processing.tasks.demo.demo_task")
def demo_task(self, seconds: int = 5) -> dict[str, Any]:
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
