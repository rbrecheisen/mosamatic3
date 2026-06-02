from typing import Any
from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, UniqueConstraint, Column, JSON


def utc_now() -> datetime:
  return datetime.now(timezone.utc)


class User(SQLModel, table=True):
  id: UUID = Field(default_factory=uuid4, primary_key=True)
  email: str = Field(index=True, unique=True)
  hashed_password: str
  is_active: bool = True
  is_admin: bool = False
  created_at: datetime = Field(default_factory=utc_now)


# class Dataset(SQLModel, table=True):
#   __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_dataset_owner_name"),)
#   id: UUID = Field(default_factory=uuid4, primary_key=True)
#   owner_id: UUID = Field(index=True, foreign_key="user.id")
#   name: str = Field(index=True)
#   created_at: datetime = Field(default_factory=utc_now)


class Dataset(SQLModel, table=True):
  __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_dataset_owner_name"),)
  id: UUID = Field(default_factory=uuid4, primary_key=True)
  owner_id: UUID = Field(index=True, foreign_key="user.id")
  name: str = Field(index=True)
  kind: str = Field(default="input", index=True)
  source_task_key: str | None = Field(default=None, index=True)
  source_task_id: str | None = Field(default=None, index=True)
  created_at: datetime = Field(default_factory=utc_now)


class DatasetFile(SQLModel, table=True):
  id: UUID = Field(default_factory=uuid4, primary_key=True)
  dataset_id: UUID = Field(index=True, foreign_key="dataset.id")
  relative_path: str
  size_bytes: int
  created_at: datetime = Field(default_factory=utc_now)


class TaskParameters(SQLModel, table=True):
  __table_args__ = (UniqueConstraint("owner_id", "task_key", name="uq_task_parameters_owner_task"),)
  id: UUID = Field(default_factory=uuid4, primary_key=True)
  owner_id: UUID = Field(index=True, foreign_key="user.id")
  task_key: str = Field(index=True)
  parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
  is_valid: bool = True
  error_message: str | None = None
  created_at: datetime = Field(default_factory=utc_now)
  updated_at: datetime = Field(default_factory=utc_now)


class FormSubmission(SQLModel, table=True):
  id: UUID = Field(default_factory=uuid4, primary_key=True)
  owner_id: UUID = Field(index=True, foreign_key="user.id")
  text_value: str
  enabled: bool = False
  choice: str
  notes: str | None = None
  created_at: datetime = Field(default_factory=utc_now)