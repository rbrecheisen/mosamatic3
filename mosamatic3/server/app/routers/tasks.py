from fastapi import APIRouter, Depends, Query, status
from ..services.authservice import get_current_user
from ..data.models import User
from ..services.taskservice import get_celery_task_status, start_demo_celery_task

router = APIRouter()


@router.post("/demo", status_code=status.HTTP_202_ACCEPTED)
def start_demo_task(
    seconds: int = Query(default=5, ge=1, le=300),
    _: User = Depends(get_current_user),
) -> dict[str, str]:
    return start_demo_celery_task(seconds)


@router.get("/{task_id}")
def get_task_status(
    task_id: str,
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    return get_celery_task_status(task_id)