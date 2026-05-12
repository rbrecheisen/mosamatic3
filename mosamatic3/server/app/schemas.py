from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
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
    id: int
    text_value: str
    enabled: bool
    choice: str
    notes: str | None
    created_at: datetime


class UploadResult(BaseModel):
    saved_files: list[str]
