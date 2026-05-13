from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, UniqueConstraint


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class Dataset(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_dataset_owner_name"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(index=True, foreign_key="user.id")
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)


class DatasetFile(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    dataset_id: UUID = Field(index=True, foreign_key="dataset.id")
    relative_path: str
    size_bytes: int
    created_at: datetime = Field(default_factory=utc_now)


class FormSubmission(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(index=True, foreign_key="user.id")
    text_value: str
    enabled: bool = False
    choice: str
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)