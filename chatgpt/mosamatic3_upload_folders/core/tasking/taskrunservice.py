from django.utils import timezone
from ..models import TaskRun

def create_task_run(owner, task_key: str, celery_task_id: str) -> TaskRun:
    return TaskRun.objects.create(owner=owner, task_key=task_key, celery_task_id=celery_task_id, status='queued', cancel_requested=False)

def request_task_cancel(celery_task_id: str, current_user):
    task_run = TaskRun.objects.filter(owner=current_user, celery_task_id=celery_task_id).first()
    if task_run is None:
        return None
    task_run.cancel_requested = True
    task_run.status = 'cancel_requested'
    task_run.updated_at = timezone.now()
    task_run.save(update_fields=['cancel_requested', 'status', 'updated_at'])
    return task_run

def is_cancel_requested(celery_task_id: str | None) -> bool:
    if celery_task_id is None:
        return False
    return TaskRun.objects.filter(celery_task_id=celery_task_id, cancel_requested=True).exists()

def mark_task_run_status(celery_task_id: str | None, status: str) -> None:
    if celery_task_id is None:
        return
    TaskRun.objects.filter(celery_task_id=celery_task_id).update(status=status, updated_at=timezone.now())
