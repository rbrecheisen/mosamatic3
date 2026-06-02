import shutil
import zipfile
from io import BytesIO
from dataclasses import dataclass
from typing import Any
from pathlib import Path, PurePosixPath
from uuid import UUID
from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select
from ..config.config import settings
from ..data.models import Dataset, DatasetFile, User
from ..data.schemas import DatasetFileRead, DatasetRead


@dataclass(frozen=True)
class OutputDatasetFile:
  relative_path: str
  content: bytes


def safe_relative_path(filename: str) -> Path:
  posix_path = PurePosixPath(filename.replace("\\", "/"))
  parts = [part for part in posix_path.parts if part not in ("", ".")]
  if not parts or any(part == ".." for part in parts):
    raise HTTPException(status_code=400, detail=f"Unsafe filename: {filename}")
  return Path(*parts)


# def dataset_to_read(dataset: Dataset, files: list[DatasetFile]) -> DatasetRead:
#   return DatasetRead(
#     id=dataset.id,
#     name=dataset.name,
#     created_at=dataset.created_at,
#     file_count=len(files),
#     total_size_bytes=sum(file.size_bytes for file in files),
#     files=[
#       DatasetFileRead(
#         id=file.id,
#         relative_path=file.relative_path,
#         size_bytes=file.size_bytes,
#         created_at=file.created_at,
#       )
#       for file in files
#     ],
#   )


def dataset_to_read(dataset: Dataset, files: list[DatasetFile]) -> DatasetRead:
  return DatasetRead(
    id=dataset.id,
    name=dataset.name,
    kind=dataset.kind,
    source_task_key=dataset.source_task_key,
    source_task_id=dataset.source_task_id,
    created_at=dataset.created_at,
    file_count=len(files),
    total_size_bytes=sum(file.size_bytes for file in files),
    files=[
      DatasetFileRead(
        id=file.id,
        relative_path=file.relative_path,
        size_bytes=file.size_bytes,
        created_at=file.created_at,
      )
      for file in files
    ],
  )


async def create_dataset_for_user(
  name: str,
  files: list[UploadFile],
  current_user: User,
  session: Session,
) -> DatasetRead:
  dataset_name = name.strip()
  if not dataset_name:
    raise HTTPException(status_code=400, detail="Dataset name is required")
  if not files:
    raise HTTPException(status_code=400, detail="At least one file is required")
  existing = session.exec(
    select(Dataset).where(
      Dataset.owner_id == current_user.id,
      Dataset.name == dataset_name,
    )
  ).first()
  if existing:
    raise HTTPException(
      status_code=400,
      detail="A dataset with this name already exists",
    )
  dataset = Dataset(
    owner_id=current_user.id, 
    name=dataset_name,
    kind="input",
  )
  session.add(dataset)
  dataset_upload_root = settings.upload_root / str(current_user.id) / str(dataset.id)
  dataset_upload_root.mkdir(parents=True, exist_ok=False)
  dataset_files: list[DatasetFile] = []
  for upload in files:
    relative_path = safe_relative_path(upload.filename or "uploaded_file")
    target_path = dataset_upload_root / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    size_bytes = 0
    with target_path.open("wb") as out_file:
      while chunk := await upload.read(1024 * 1024):
        size_bytes += len(chunk)
        out_file.write(chunk)
    dataset_file = DatasetFile(
      dataset_id=dataset.id,
      relative_path=relative_path.as_posix(),
      size_bytes=size_bytes,
    )
    session.add(dataset_file)
    dataset_files.append(dataset_file)
  session.commit()
  session.refresh(dataset)
  for dataset_file in dataset_files:
    session.refresh(dataset_file)
  return dataset_to_read(dataset, dataset_files)


def list_datasets_for_user(
  current_user: User,
  session: Session,
) -> list[DatasetRead]:
  datasets = session.exec(
    select(Dataset)
    .where(Dataset.owner_id == current_user.id)
    .order_by(Dataset.created_at.desc())
  ).all()
  return [
    dataset_to_read(dataset, get_dataset_files(dataset.id, session))
    for dataset in datasets
  ]


def get_dataset_for_user(
  dataset_id: UUID,
  current_user: User,
  session: Session,
) -> DatasetRead:
  dataset = session.exec(
    select(Dataset).where(
      Dataset.id == dataset_id,
      Dataset.owner_id == current_user.id,
    )
  ).first()
  if dataset is None:
    raise HTTPException(status_code=404, detail="Dataset not found")
  files = get_dataset_files(dataset.id, session)
  return dataset_to_read(dataset, files)


def delete_dataset_for_user(
  dataset_id: UUID,
  current_user: User,
  session: Session,
) -> None:
  dataset = session.exec(
    select(Dataset).where(
      Dataset.id == dataset_id,
      Dataset.owner_id == current_user.id,
    )
  ).first()
  if dataset is None:
    raise HTTPException(status_code=404, detail="Dataset not found")
  delete_dataset_and_files(dataset, current_user.id, session)


def get_dataset_files(
  dataset_id: UUID,
  session: Session,
) -> list[DatasetFile]:
  return list(
    session.exec(
      select(DatasetFile)
      .where(DatasetFile.dataset_id == dataset_id)
      .order_by(DatasetFile.relative_path)
    )
  )


def delete_dataset_and_files(
  dataset: Dataset,
  owner_id: UUID,
  session: Session,
) -> None:
  dataset_files = session.exec(
    select(DatasetFile).where(DatasetFile.dataset_id == dataset.id)
  ).all()
  for dataset_file in dataset_files:
    session.delete(dataset_file)
  session.delete(dataset)
  session.commit()
  dataset_upload_root = settings.upload_root / str(owner_id) / str(dataset.id)
  shutil.rmtree(dataset_upload_root, ignore_errors=True)


def make_unique_dataset_name(
  base_name: str,
  owner_id: UUID,
  session: Session,
) -> str:
  normalized_base_name = base_name.strip()
  if not normalized_base_name:
    normalized_base_name = "Output dataset"
  existing_names = set(
    session.exec(
      select(Dataset.name).where(Dataset.owner_id == owner_id)
    ).all()
  )
  if normalized_base_name not in existing_names:
    return normalized_base_name
  counter = 2
  while True:
    candidate_name = f"{normalized_base_name} ({counter})"
    if candidate_name not in existing_names:
      return candidate_name
    counter += 1


def create_output_dataset_for_user_id(
  name: str,
  files: list[OutputDatasetFile],
  user_id: UUID,
  session: Session,
  source_task_key: str | None = None,
  source_task_id: str | None = None,
) -> DatasetRead:
  if not files:
    raise ValueError("An output dataset must contain at least one file.")
  user = session.get(User, user_id)
  if user is None:
    raise ValueError(f"User not found: {user_id}")
  dataset_name = make_unique_dataset_name(name, user_id, session)
  dataset = Dataset(
    owner_id=user_id,
    name=dataset_name,
    kind="output",
    source_task_key=source_task_key,
    source_task_id=source_task_id,
  )
  session.add(dataset)
  session.flush()
  dataset_upload_root = settings.upload_root / str(user_id) / str(dataset.id)
  dataset_upload_root.mkdir(parents=True, exist_ok=False)
  dataset_files: list[DatasetFile] = []
  try:
    for output_file in files:
      relative_path = safe_relative_path(output_file.relative_path)
      target_path = dataset_upload_root / relative_path
      target_path.parent.mkdir(parents=True, exist_ok=True)
      target_path.write_bytes(output_file.content)
      dataset_file = DatasetFile(
        dataset_id=dataset.id,
        relative_path=relative_path.as_posix(),
        size_bytes=target_path.stat().st_size,
      )
      session.add(dataset_file)
      dataset_files.append(dataset_file)
    session.commit()
    session.refresh(dataset)
    for dataset_file in dataset_files:
      session.refresh(dataset_file)
    return dataset_to_read(dataset, dataset_files)
  except Exception:
    session.rollback()
    shutil.rmtree(dataset_upload_root, ignore_errors=True)
    raise


def create_dataset_zip_for_user(
  dataset_id: UUID,
  current_user: User,
  session: Session,
) -> tuple[str, bytes]:
  dataset = session.get(Dataset, dataset_id)
  if dataset is None or dataset.owner_id != current_user.id:
    raise ValueError("Dataset not found")
  files = session.exec(
    select(DatasetFile).where(DatasetFile.dataset_id == dataset.id)
  ).all()
  dataset_root = settings.upload_root / str(current_user.id) / str(dataset.id)
  zip_buffer = BytesIO()
  with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
    for dataset_file in files:
      source_path = dataset_root / dataset_file.relative_path
      if not source_path.exists() or not source_path.is_file():
        continue
      zip_file.write(
        source_path,
        arcname=dataset_file.relative_path,
      )
  safe_name = dataset.name.replace(" ", "_")
  filename = f"{safe_name}.zip"
  return filename, zip_buffer.getvalue()