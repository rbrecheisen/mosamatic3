from fastapi import APIRouter, Depends, status, HTTPException
from sqlmodel import Session
from ..data.database import get_session
from ..data.models import User
from ..data.schemas import TaskParametersRead, TaskParametersSave
from ..services.authservice import get_current_user
from ..services.taskservice import (
  get_celery_task_status,
  get_saved_task_parameters,
  save_task_parameters,
  start_task_by_key,
)
from ..tasks.registry import TASKS

router = APIRouter()


@router.get("")
def list_tasks(
  _: User = Depends(get_current_user),
) -> list[dict[str, str | None]]:
  return [
    {
      "id": task.key,
      "name": task.name,
      "description": task.description,
    }
    for task in TASKS.values()
  ]


@router.get("/{task_key}/schema")
def get_task_schema(
  task_key: str,
  _: User = Depends(get_current_user),
) -> dict[str, object]:
  task = TASKS.get(task_key)
  if task is None:
    raise HTTPException(
      status_code=404,
      detail=f"Unknown task: {task_key}",
    )
  return {
    "id": task.key,
    "name": task.name,
    "description": task.description,
    "schema": task.parameter_schema.model_json_schema(),
  }


@router.get("/{task_key}/parameters", response_model=TaskParametersRead)
def read_task_parameters(
  task_key: str,
  current_user: User = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> TaskParametersRead:
  return get_saved_task_parameters(task_key, current_user, session)


@router.post("/{task_key}/parameters", response_model=TaskParametersRead)
def update_task_parameters(
  task_key: str,
  payload: TaskParametersSave,
  current_user: User = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> TaskParametersRead:
  return save_task_parameters(task_key, payload, current_user, session)


@router.post("/{task_key}/run", status_code=status.HTTP_202_ACCEPTED)
def run_task(
  task_key: str,
  current_user: User = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> dict[str, str]:
  return start_task_by_key(task_key, current_user, session)


@router.get("/{task_id}")
def get_task_status(
  task_id: str,
  _: User = Depends(get_current_user),
) -> dict[str, object]:
  return get_celery_task_status(task_id)