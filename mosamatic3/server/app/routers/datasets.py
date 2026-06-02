from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlmodel import Session
from ..services.authservice import get_current_user
from ..data.database import get_session
from ..data.models import User
from ..data.schemas import DatasetRead
from ..services.datasetservice import (
  create_dataset_for_user,
  delete_dataset_for_user,
  get_dataset_for_user,
  list_datasets_for_user,
)

router = APIRouter()


@router.post("", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def create_dataset(
  name: str = Form(...),
  files: list[UploadFile] = File(...),
  current_user: User = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> DatasetRead:
  return await create_dataset_for_user(name, files, current_user, session)


@router.get("", response_model=list[DatasetRead])
def list_datasets(
  current_user: User = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> list[DatasetRead]:
  return list_datasets_for_user(current_user, session)


@router.get("/{dataset_id}", response_model=DatasetRead)
def get_dataset(
  dataset_id: UUID,
  current_user: User = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> DatasetRead:
  return get_dataset_for_user(dataset_id, current_user, session)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
  dataset_id: UUID,
  current_user: User = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> None:
  delete_dataset_for_user(dataset_id, current_user, session)