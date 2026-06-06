from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar
from celery.exceptions import Ignore
from pydantic import BaseModel
from .models import Dataset
from .dataset_service import OutputDatasetFile, create_output_dataset_for_user_id, get_dataset_file_path
from .taskrun_service import is_cancel_requested, mark_task_run_status

TParams = TypeVar('TParams', bound=BaseModel)

@dataclass
class TaskDatasetFile:
    file: Any
    path: Path
    index: int
    current: int
    total: int

class TaskRuntime:
    def __init__(self, *, task_key: str, parameters: dict, parameter_model: type[TParams], user_id: str, celery_task: Any | None = None):
        self.task_key = task_key
        self.params = parameter_model.model_validate(parameters)
        self.user_id = user_id
        self.celery_task = celery_task
        self.task_id = getattr(getattr(celery_task, 'request', None), 'id', None) if celery_task else None

    def update_progress(self, *, current: int, total: int, message: str, state: str = 'PROGRESS') -> None:
        if self.celery_task is None:
            return
        self.celery_task.update_state(state=state, meta={'current': current, 'total': total, 'message': message})

    def check_cancelled(self, *, current: int, total: int, message: str) -> None:
        if not is_cancel_requested(self.task_id):
            return
        mark_task_run_status(self.task_id, 'cancelled')
        self.update_progress(state='REVOKED', current=current, total=total, message=message)
        raise Ignore()

    def mark_running(self):
        mark_task_run_status(self.task_id, 'running')

    def mark_finished(self):
        mark_task_run_status(self.task_id, 'finished')

    def mark_failed(self):
        mark_task_run_status(self.task_id, 'failed')

    def get_input_dataset(self, dataset_id) -> Dataset:
        return Dataset.objects.get(id=dataset_id, owner_id=self.user_id)

    def iter_dataset_files(self, dataset: Dataset, *, message_factory: Callable[[int, int], str]) -> Iterator[TaskDatasetFile]:
        files = list(dataset.files.all())
        total = len(files)
        for index, dataset_file in enumerate(files):
            current = index + 1
            self.check_cancelled(current=index, total=total, message=f'Task cancelled after {index} of {total} files')
            file_path = get_dataset_file_path(self.user_id, dataset.id, dataset_file.relative_path)
            yield TaskDatasetFile(file=dataset_file, path=file_path, index=index, current=current, total=total)
            self.update_progress(current=current, total=total, message=message_factory(current, total))

    def create_output_dataset(self, *, name: str, files: list[OutputDatasetFile]):
        return create_output_dataset_for_user_id(name=name, files=files, user_id=self.user_id, source_task_key=self.task_key, source_task_id=self.task_id)
