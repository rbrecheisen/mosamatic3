from typing import Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class UserCreate(BaseModel):
  email: str
  password: str


class UserRead(BaseModel):
  id: UUID
  email: str
  is_active: bool
  is_admin: bool
  created_at: datetime


class AdminSummary(BaseModel):
  user_count: int
  dataset_count: int
  dataset_file_count: int


class AdminUserRead(BaseModel):
  id: UUID
  email: str
  is_active: bool
  is_admin: bool
  created_at: datetime


class Token(BaseModel):
  access_token: str
  token_type: str = "bearer"


class FormSubmissionCreate(BaseModel):
  text_value: str
  enabled: bool = False
  choice: str
  notes: str | None = None


class FormSubmissionRead(BaseModel):
  id: UUID
  text_value: str
  enabled: bool
  choice: str
  notes: str | None
  created_at: datetime


class DatasetFileRead(BaseModel):
  id: UUID
  relative_path: str
  size_bytes: int
  created_at: datetime


# class DatasetRead(BaseModel):
#   id: UUID
#   name: str
#   created_at: datetime
#   file_count: int
#   total_size_bytes: int
#   files: list[DatasetFileRead] = []


class DatasetRead(BaseModel):
  id: UUID
  name: str
  kind: str
  source_task_key: str | None = None
  source_task_id: str | None = None
  created_at: datetime
  file_count: int
  total_size_bytes: int
  files: list[DatasetFileRead] = []


# class AdminDatasetRead(BaseModel):
#   id: UUID
#   name: str
#   owner_id: UUID
#   created_at: datetime
#   file_count: int
#   total_size_bytes: int


class AdminDatasetRead(BaseModel):
  id: UUID
  name: str
  kind: str
  source_task_key: str | None = None
  source_task_id: str | None = None
  owner_id: UUID
  created_at: datetime
  file_count: int
  total_size_bytes: int


class TaskParametersSave(BaseModel):
  task_key: str
  parameters: dict[str, Any]


class TaskParametersRead(BaseModel):
  task_key: str
  parameters: dict[str, Any]
  is_valid: bool
  error_message: str | None = None
  exists: bool = True
  updated_at: datetime | None = None