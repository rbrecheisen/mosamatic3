from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.data.models import User
from app.services.datasetservice import (
  OutputDatasetFile,
  create_output_dataset_for_user_id,
  safe_relative_path,
)


def test_safe_relative_path_normalizes_windows_and_posix_paths() -> None:
  assert safe_relative_path(r"series\\slice1.dcm").as_posix() == "series/slice1.dcm"
  assert safe_relative_path("series/slice2.dcm").as_posix() == "series/slice2.dcm"


@pytest.mark.parametrize("filename", ["", ".", "../evil.dcm", "series/../evil.dcm"])
def test_safe_relative_path_rejects_unsafe_paths(filename: str) -> None:
  with pytest.raises(HTTPException) as exc_info:
    safe_relative_path(filename)

  assert exc_info.value.status_code == 400


def test_create_output_dataset_creates_unique_names_and_files(session, tmp_path, monkeypatch) -> None:
  user = User(email="owner@example.com", hashed_password="hash")
  session.add(user)
  session.commit()
  session.refresh(user)

  first = create_output_dataset_for_user_id(
    name="Task output",
    files=[OutputDatasetFile(relative_path="summary.json", content=b"{}")],
    user_id=user.id,
    session=session,
    source_task_key="demo",
    source_task_id="task-1",
  )
  second = create_output_dataset_for_user_id(
    name="Task output",
    files=[OutputDatasetFile(relative_path="summary.json", content=b"{}")],
    user_id=user.id,
    session=session,
    source_task_key="demo",
    source_task_id="task-2",
  )

  assert first.name == "Task output"
  assert second.name == "Task output (2)"
  assert first.kind == "output"
  assert first.source_task_key == "demo"
  assert first.file_count == 1


def test_create_output_dataset_rejects_missing_user(session) -> None:
  with pytest.raises(ValueError, match="User not found"):
    create_output_dataset_for_user_id(
      name="Task output",
      files=[OutputDatasetFile(relative_path="summary.json", content=b"{}")],
      user_id=uuid4(),
      session=session,
    )
