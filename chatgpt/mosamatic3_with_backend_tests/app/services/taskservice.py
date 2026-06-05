from typing import Any
from uuid import UUID
from celery.result import AsyncResult
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlmodel import Session, select
from ..data.models import Dataset, TaskParameters, User, utc_now
from ..data.schemas import TaskParametersRead, TaskParametersSave
from ..celeryapp import celery_app
from ..tasks.registry import TASKS


def get_task_definition_or_404(task_key: str):
  task = TASKS.get(task_key)
  if task is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"Unknown task: {task_key}",
    )
  return task


def get_dataset_for_user_or_404(
  raw_dataset_id: Any,
  current_user: User,
  session: Session,
) -> str:
  try:
    dataset_id = UUID(str(raw_dataset_id))
  except (TypeError, ValueError):
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail=f"Invalid dataset id: {raw_dataset_id}",
    )
  dataset = session.exec(
    select(Dataset).where(
      Dataset.owner_id == current_user.id,
      Dataset.id == dataset_id,
    )
  ).first()
  if dataset is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"Dataset not found: {dataset_id}",
    )
  return str(dataset_id)


def validate_dataset_references(
  parameters: dict[str, Any],
  current_user: User,
  session: Session,
) -> None:
  for field_name in ["dataset_id", "single_dataset_id"]:
    raw_dataset_id = parameters.get(field_name)
    if raw_dataset_id not in (None, ""):
      get_dataset_for_user_or_404(raw_dataset_id, current_user, session)
  raw_dataset_ids = parameters.get("dataset_ids")
  if raw_dataset_ids in (None, ""):
    return
  if not isinstance(raw_dataset_ids, list):
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail="'dataset_ids' must be a list.",
    )
  for raw_dataset_id in raw_dataset_ids:
    get_dataset_for_user_or_404(raw_dataset_id, current_user, session)


def validate_task_parameters(
  task_key: str,
  parameters: dict[str, Any],
  current_user: User,
  session: Session,
) -> dict[str, Any]:
  task = get_task_definition_or_404(task_key)
  try:
    validated_model = task.parameter_schema.model_validate(parameters)
  except ValidationError as exc:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail=exc.errors(),
    ) from exc
  validated_parameters = validated_model.model_dump(mode="json")
  validate_dataset_references(
    validated_parameters,
    current_user,
    session,
  )
  return validated_parameters


def get_saved_task_parameters(
  task_key: str,
  current_user: User,
  session: Session,
) -> TaskParametersRead:
  get_task_definition_or_404(task_key)
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
  task = get_task_definition_or_404(task_key)
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
  celery_result = celery_app.send_task(
    task.celery_task_name,
    args=[
      parameters,
      str(current_user.id),
    ],
  )
  return {
    "task_id": celery_result.id,
    "status": "queued",
  }


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