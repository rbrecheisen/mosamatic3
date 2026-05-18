from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr


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


class DatasetRead(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    file_count: int
    total_size_bytes: int
    files: list[DatasetFileRead] = []


class AdminDatasetRead(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime
    file_count: int
    total_size_bytes: int