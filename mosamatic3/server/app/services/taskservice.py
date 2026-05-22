from celery.result import AsyncResult
from ..processing.app import celery_app
from ..processing.tasks.demo.demotask import demotask


def start_demo_celery_task(seconds: int) -> dict[str, str]:
    task = demotask.delay(seconds)
    return {"task_id": task.id, "status": "queued"}


def get_celery_task_status(task_id: str) -> dict[str, object]:
    result = AsyncResult(task_id, app=celery_app)
    response: dict[str, object] = {
        "task_id": task_id,
        "state": result.state,
    }
    if result.state == "PENDING":
        response["message"] = "Task is pending or unknown"
    elif result.state == "FAILURE":
        response["message"] = str(result.info)
    elif isinstance(result.info, dict):
        response.update(result.info)
    elif result.ready():
        response["result"] = result.result
    return response