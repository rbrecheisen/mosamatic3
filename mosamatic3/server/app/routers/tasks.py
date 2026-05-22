from fastapi import APIRouter, Depends, Query, status
from ..services.authservice import get_current_user
from ..data.models import User
from ..services.taskservice import (
  get_celery_task_status, 
  start_demotask,
  start_rescaledicomimagestask,
)

router = APIRouter()


@router.post("/demo", status_code=status.HTTP_202_ACCEPTED)
def demotask(
    seconds: int = Query(default=5, ge=1, le=300),
    _: User = Depends(get_current_user),
) -> dict[str, str]:
    return start_demotask(seconds)


@router.post("/rescaledicomimages", status_code=status.HTTP_202_ACCEPTED)
def rescaledicomimagestask() -> dict[str, str]:
    return start_rescaledicomimagestask()


@router.get("/{task_id}")
def get_task_status(
    task_id: str,
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    return get_celery_task_status(task_id)