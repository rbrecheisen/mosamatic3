import shutil, zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError, NotFound
from ..models import Dataset, DatasetFile

@dataclass(frozen=True)
class OutputDatasetFile:
    relative_path: str
    content: bytes

def safe_relative_path(filename: str) -> Path:
    posix_path = PurePosixPath(filename.replace('\\', '/'))
    parts = [part for part in posix_path.parts if part not in ('', '.')]
    if not parts or any(part == '..' for part in parts):
        raise ValidationError(f'Unsafe filename: {filename}')
    return Path(*parts)

def dataset_upload_root(user_id, dataset_id) -> Path:
    return settings.UPLOAD_ROOT / str(user_id) / str(dataset_id)

def get_dataset_file_path(user_id, dataset_id, relative_path: str) -> Path:
    file_path = dataset_upload_root(user_id, dataset_id) / safe_relative_path(relative_path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f'Dataset file not found: {file_path}')
    return file_path

def create_dataset_for_user(name: str, files, user, relative_paths=None) -> Dataset:
    dataset_name = name.strip()
    if not dataset_name:
        raise ValidationError('Dataset name is required')
    if not files:
        raise ValidationError('At least one file is required')
    if Dataset.objects.filter(owner=user, name=dataset_name).exists():
        raise ValidationError('A dataset with this name already exists')

    relative_paths = list(relative_paths or [])
    if relative_paths and len(relative_paths) != len(files):
        raise ValidationError('The number of relative paths does not match the number of uploaded files')

    if not relative_paths:
        relative_paths = [getattr(upload, 'name', '') or 'uploaded_file' for upload in files]

    safe_paths = [safe_relative_path(path) for path in relative_paths]
    safe_path_strings = [path.as_posix() for path in safe_paths]
    if len(safe_path_strings) != len(set(safe_path_strings)):
        raise ValidationError('The upload contains duplicate relative file paths')

    root = None
    try:
        with transaction.atomic():
            dataset = Dataset.objects.create(owner=user, name=dataset_name, kind='input')
            root = dataset_upload_root(user.id, dataset.id)
            root.mkdir(parents=True, exist_ok=False)

            for upload, relative_path in zip(files, safe_paths):
                target_path = root / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                size_bytes = 0
                with target_path.open('wb') as out_file:
                    for chunk in upload.chunks():
                        size_bytes += len(chunk)
                        out_file.write(chunk)
                DatasetFile.objects.create(dataset=dataset, relative_path=relative_path.as_posix(), size_bytes=size_bytes)
            return dataset
    except Exception:
        if root is not None:
            shutil.rmtree(root, ignore_errors=True)
        raise

def delete_dataset_and_files(dataset: Dataset) -> None:
    root = dataset_upload_root(dataset.owner_id, dataset.id)
    dataset.delete()
    shutil.rmtree(root, ignore_errors=True)

def make_unique_dataset_name(base_name: str, user) -> str:
    base = base_name.strip() or 'Output dataset'
    existing = set(Dataset.objects.filter(owner=user).values_list('name', flat=True))
    if base not in existing:
        return base
    counter = 2
    while True:
        candidate = f'{base} ({counter})'
        if candidate not in existing:
            return candidate
        counter += 1

def create_output_dataset_for_user_id(name: str, files: list[OutputDatasetFile], user_id, source_task_key=None, source_task_id=None) -> Dataset:
    from django.contrib.auth.models import User
    if not files:
        raise ValueError('An output dataset must contain at least one file.')
    user = User.objects.get(id=user_id)
    dataset = Dataset.objects.create(
        owner=user,
        name=make_unique_dataset_name(name, user),
        kind='output',
        source_task_key=source_task_key,
        source_task_id=source_task_id,
    )
    root = dataset_upload_root(user.id, dataset.id)
    root.mkdir(parents=True, exist_ok=False)
    for out in files:
        relative = safe_relative_path(out.relative_path)
        target_path = root / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(out.content)
        DatasetFile.objects.create(dataset=dataset, relative_path=relative.as_posix(), size_bytes=len(out.content))
    return dataset

def create_dataset_zip_for_user(dataset_id, user):
    try:
        dataset = Dataset.objects.get(id=dataset_id, owner=user)
    except Dataset.DoesNotExist:
        raise NotFound('Dataset not found')
    zip_buffer = BytesIO()
    root = dataset_upload_root(user.id, dataset.id)
    with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for item in dataset.files.all():
            file_path = root / safe_relative_path(item.relative_path)
            if file_path.exists() and file_path.is_file():
                zf.write(file_path, arcname=item.relative_path)
    return f'{dataset.name}.zip'.replace('/', '_'), zip_buffer.getvalue()

# import shutil, zipfile
# from dataclasses import dataclass
# from io import BytesIO
# from pathlib import Path, PurePosixPath
# from django.conf import settings
# from rest_framework.exceptions import ValidationError, NotFound
# from ..models import Dataset, DatasetFile

# @dataclass(frozen=True)
# class OutputDatasetFile:
#     relative_path: str
#     content: bytes

# def safe_relative_path(filename: str) -> Path:
#     posix_path = PurePosixPath(filename.replace('\\', '/'))
#     parts = [part for part in posix_path.parts if part not in ('', '.')]
#     if not parts or any(part == '..' for part in parts):
#         raise ValidationError(f'Unsafe filename: {filename}')
#     return Path(*parts)

# def dataset_upload_root(user_id, dataset_id) -> Path:
#     return settings.UPLOAD_ROOT / str(user_id) / str(dataset_id)

# def get_dataset_file_path(user_id, dataset_id, relative_path: str) -> Path:
#     file_path = dataset_upload_root(user_id, dataset_id) / safe_relative_path(relative_path)
#     if not file_path.exists() or not file_path.is_file():
#         raise FileNotFoundError(f'Dataset file not found: {file_path}')
#     return file_path

# def create_dataset_for_user(name: str, files, user) -> Dataset:
#     dataset_name = name.strip()
#     if not dataset_name:
#         raise ValidationError('Dataset name is required')
#     if not files:
#         raise ValidationError('At least one file is required')
#     if Dataset.objects.filter(owner=user, name=dataset_name).exists():
#         raise ValidationError('A dataset with this name already exists')
#     dataset = Dataset.objects.create(owner=user, name=dataset_name, kind='input')
#     root = dataset_upload_root(user.id, dataset.id)
#     root.mkdir(parents=True, exist_ok=False)
#     for upload in files:
#         relative_path = safe_relative_path(getattr(upload, 'name', '') or 'uploaded_file')
#         target_path = root / relative_path
#         target_path.parent.mkdir(parents=True, exist_ok=True)
#         size_bytes = 0
#         with target_path.open('wb') as out_file:
#             for chunk in upload.chunks():
#                 size_bytes += len(chunk)
#                 out_file.write(chunk)
#         DatasetFile.objects.create(dataset=dataset, relative_path=relative_path.as_posix(), size_bytes=size_bytes)
#     return dataset

# def delete_dataset_and_files(dataset: Dataset) -> None:
#     root = dataset_upload_root(dataset.owner_id, dataset.id)
#     dataset.delete()
#     shutil.rmtree(root, ignore_errors=True)

# def make_unique_dataset_name(base_name: str, user) -> str:
#     base = base_name.strip() or 'Output dataset'
#     existing = set(Dataset.objects.filter(owner=user).values_list('name', flat=True))
#     if base not in existing:
#         return base
#     counter = 2
#     while True:
#         candidate = f'{base} ({counter})'
#         if candidate not in existing:
#             return candidate
#         counter += 1

# def create_output_dataset_for_user_id(name: str, files: list[OutputDatasetFile], user_id, source_task_key=None, source_task_id=None) -> Dataset:
#     from django.contrib.auth.models import User
#     if not files:
#         raise ValueError('An output dataset must contain at least one file.')
#     user = User.objects.get(id=user_id)
#     dataset = Dataset.objects.create(
#         owner=user,
#         name=make_unique_dataset_name(name, user),
#         kind='output',
#         source_task_key=source_task_key,
#         source_task_id=source_task_id,
#     )
#     root = dataset_upload_root(user.id, dataset.id)
#     root.mkdir(parents=True, exist_ok=False)
#     for out in files:
#         relative = safe_relative_path(out.relative_path)
#         target_path = root / relative
#         target_path.parent.mkdir(parents=True, exist_ok=True)
#         target_path.write_bytes(out.content)
#         DatasetFile.objects.create(dataset=dataset, relative_path=relative.as_posix(), size_bytes=len(out.content))
#     return dataset

# def create_dataset_zip_for_user(dataset_id, user):
#     try:
#         dataset = Dataset.objects.get(id=dataset_id, owner=user)
#     except Dataset.DoesNotExist:
#         raise NotFound('Dataset not found')
#     zip_buffer = BytesIO()
#     root = dataset_upload_root(user.id, dataset.id)
#     with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
#         for item in dataset.files.all():
#             file_path = root / safe_relative_path(item.relative_path)
#             if file_path.exists() and file_path.is_file():
#                 zf.write(file_path, arcname=item.relative_path)
#     return f'{dataset.name}.zip'.replace('/', '_'), zip_buffer.getvalue()
