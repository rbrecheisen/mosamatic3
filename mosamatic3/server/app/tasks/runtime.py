from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar
from uuid import UUID
from celery.exceptions import Ignore
from pydantic import BaseModel
from sqlmodel import Session
from app.data.database import engine
from app.data.models import User
from app.data.schemas import DatasetFileRead, DatasetRead
from app.services.datasetservice import (
  OutputDatasetFile,
  create_output_dataset_for_user_id,
  get_dataset_file_path,
  get_dataset_for_user,
)
from app.services.taskrunservice import (
  is_cancel_requested,
  mark_task_run_status,
)

TParams = TypeVar("TParams", bound=BaseModel)


@dataclass
class TaskDatasetFile:
  file: DatasetFileRead
  path: Path
  index: int
  current: int
  total: int


class TaskRuntime:
  def __init__(
    self,
    *,
    task_key: str,
    parameters: dict,
    parameter_model: type[TParams],
    user_id: str,
    celery_task: Any | None = None,
  ) -> None:
    self.task_key = task_key
    self.params = parameter_model.model_validate(parameters)
    self.user_id = user_id
    self.user_uuid = UUID(user_id)
    self.celery_task = celery_task
    self.task_id = self._get_celery_task_id()

  def _get_celery_task_id(self) -> str | None:
    if self.celery_task is None:
      return None
    request = getattr(self.celery_task, "request", None)
    if request is None:
      return None
    return request.id

  def update_progress(
    self,
    *,
    current: int,
    total: int,
    message: str,
    state: str = "PROGRESS",
  ) -> None:
    if self.celery_task is None:
      return

    self.celery_task.update_state(
      state=state,
      meta={
        "current": current,
        "total": total,
        "message": message,
      },
    )

  def check_cancelled(
    self,
    *,
    current: int,
    total: int,
    message: str,
  ) -> None:
    if not is_cancel_requested(self.task_id):
      return

    mark_task_run_status(self.task_id, "cancelled")

    self.update_progress(
      state="REVOKED",
      current=current,
      total=total,
      message=message,
    )

    raise Ignore()

  def mark_running(self) -> None:
    mark_task_run_status(self.task_id, "running")

  def mark_finished(self) -> None:
    mark_task_run_status(self.task_id, "finished")

  def mark_failed(self) -> None:
    mark_task_run_status(self.task_id, "failed")

  def get_user(self, session: Session) -> User:
    user = session.get(User, self.user_uuid)
    if user is None:
      raise ValueError(f"User not found: {self.user_id}")
    return user

  def get_input_dataset(self, dataset_id: UUID) -> DatasetRead:
    with Session(engine) as session:
      user = self.get_user(session)
      return get_dataset_for_user(dataset_id, user, session)

  def iter_dataset_files(
    self,
    dataset: DatasetRead,
    *,
    message_factory: Callable[[int, int], str],
  ) -> Iterator[TaskDatasetFile]:
    total = dataset.file_count

    for index, dataset_file in enumerate(dataset.files):
      current = index + 1
      message = message_factory(current, total)

      self.check_cancelled(
        current=index,
        total=total,
        message=f"Task cancelled after {index} of {total} files",
      )

      file_path = get_dataset_file_path(
        user_id=self.user_uuid,
        dataset_id=dataset.id,
        relative_path=dataset_file.relative_path,
      )

      yield TaskDatasetFile(
        file=dataset_file,
        path=file_path,
        index=index,
        current=current,
        total=total,
      )

      self.update_progress(
        current=current,
        total=total,
        message=message,
      )

  def create_output_dataset(
    self,
    *,
    name: str,
    files: list[OutputDatasetFile],
  ):
    with Session(engine) as session:
      return create_output_dataset_for_user_id(
        name=name,
        files=files,
        user_id=self.user_uuid,
        session=session,
        source_task_key=self.task_key,
        source_task_id=self.task_id,
      )