from typing import Any
from uuid import UUID
from celery.result import AsyncResult
from fastapi import HTTPException, status
from sqlmodel import Session, select
from ..data.models import Dataset, TaskParameters, User, utc_now
from ..data.schemas import TaskParametersRead, TaskParametersSave
from ..processing.app import celery_app
from ..processing.tasks.demo.demotask import demotask
from ..processing.tasks.rescaledicomimages.rescaledicomimagestask import rescaledicomimagestask


def start_demotask(
  seconds: int,
  single_dataset_id: str | None,
  text_value: str,
  checkbox_value: bool,
  slider_value: float,
  dataset_ids: list[str],
) -> dict[str, str]:
  task = demotask.delay(
    seconds=seconds,
    single_dataset_id=single_dataset_id,
    text_value=text_value,
    checkbox_value=checkbox_value,
    slider_value=slider_value,
    dataset_ids=dataset_ids,
  )
  return {"task_id": task.id, "status": "queued"}


def start_rescaledicomimagestask() -> dict[str, str]:
  task = rescaledicomimagestask.delay()
  return {"task_id": task.id, "status": "queued"}


def validate_dataset_ids(
  raw_dataset_ids: Any,
  current_user: User,
  session: Session,
) -> list[str]:
  if raw_dataset_ids is None:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail="At least one dataset must be selected.",
    )
  if not isinstance(raw_dataset_ids, list):
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail="'dataset_ids' must be a list.",
    )
  dataset_ids: list[UUID] = []
  for raw_id in raw_dataset_ids:
    try:
      dataset_ids.append(UUID(str(raw_id)))
    except ValueError:
      raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Invalid dataset id: {raw_id}",
      )
  if not dataset_ids:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail="At least one dataset must be selected.",
    )
  datasets = session.exec(
    select(Dataset).where(
      Dataset.owner_id == current_user.id,
      Dataset.id.in_(dataset_ids),
    )
  ).all()
  if len(datasets) != len(dataset_ids):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="One or more datasets were not found.",
    )
  return [str(dataset_id) for dataset_id in dataset_ids]


def validate_task_parameters(
  task_key: str, 
  parameters: dict[str, Any], 
  current_user: User, 
  session: Session
) -> dict[str, Any]:
  if task_key == "demo":
    raw_seconds = parameters.get("seconds", 5)
    try:
      seconds = int(raw_seconds)
    except (TypeError, ValueError):
      raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Demo task parameter 'seconds' must be an integer.",
      )
    if seconds < 1 or seconds > 300:
      raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Demo task parameter 'seconds' must be between 1 and 300.",
      )
    dataset_ids = validate_dataset_ids(
      parameters.get("dataset_ids"),
      current_user,
      session,
    )
    return {
      "seconds": seconds,
      "dataset_ids": dataset_ids,
    }
  raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Unknown task: {task_key}",
  )


def get_saved_task_parameters(
  task_key: str,
  current_user: User,
  session: Session,
) -> TaskParametersRead:
  saved = session.exec(
    select(TaskParameters).where(
      TaskParameters.owner_id == current_user.id,
      TaskParameters.task_key == task_key,
    )
  ).first()
  if saved is None:
    return TaskParametersRead(
      task_key=task_key,
      parameters={},
      is_valid=False,
      error_message=None,
      exists=False,
      updated_at=None,
    )
  return TaskParametersRead(
    task_key=saved.task_key,
    parameters=saved.parameters,
    is_valid=saved.is_valid,
    error_message=saved.error_message,
    exists=True,
    updated_at=saved.updated_at,
  )


def save_task_parameters(
  task_key: str,
  payload: TaskParametersSave,
  current_user: User,
  session: Session,
) -> TaskParametersRead:
  if payload.task_key != task_key:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Task key in URL and request body do not match.",
    )
  validated_parameters = validate_task_parameters(
    task_key,
    payload.parameters,
    current_user,
    session,
  )
  saved = session.exec(
    select(TaskParameters).where(
      TaskParameters.owner_id == current_user.id,
      TaskParameters.task_key == task_key,
    )
  ).first()
  if saved is None:
    saved = TaskParameters(
      owner_id=current_user.id,
      task_key=task_key,
      parameters=validated_parameters,
      is_valid=True,
      error_message=None,
    )
  else:
    saved.parameters = validated_parameters
    saved.is_valid = True
    saved.error_message = None
    saved.updated_at = utc_now()
  session.add(saved)
  session.commit()
  session.refresh(saved)
  return TaskParametersRead(
    task_key=saved.task_key,
    parameters=saved.parameters,
    is_valid=saved.is_valid,
    error_message=saved.error_message,
    exists=True,
    updated_at=saved.updated_at,
  )


def start_task_by_key(
  task_key: str,
  current_user: User,
  session: Session,
) -> dict[str, str]:
  saved = session.exec(
    select(TaskParameters).where(
      TaskParameters.owner_id == current_user.id,
      TaskParameters.task_key == task_key,
    )
  ).first()
  if saved is None or not saved.is_valid:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Valid task parameters must be submitted before running this task.",
    )
  parameters = validate_task_parameters(
    task_key,
    saved.parameters,
    current_user,
    session,
  )
  if task_key == "demo":
    return start_demotask(
      seconds=parameters["seconds"],
      dataset_ids=parameters["dataset_ids"],
    )
  raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Unknown task: {task_key}",
  )


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