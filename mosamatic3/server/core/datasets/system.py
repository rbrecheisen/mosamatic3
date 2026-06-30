import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction

from core.datasets.services import dataset_upload_root, safe_relative_path
from core.models import Dataset, DatasetFile


def sync_builtin_model_files_dataset_for_user(user: User) -> Dataset | None:
    source_root = Path(settings.BUILTIN_MODEL_FILES_DIR)

    if not source_root.exists():
        return None

    source_files = [
        path
        for path in source_root.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    ]

    if not source_files:
        return None

    dataset_name = settings.BUILTIN_MODEL_FILES_DATASET_NAME

    with transaction.atomic():
        dataset, _created = Dataset.objects.get_or_create(
            owner=user,
            name=dataset_name,
            defaults={
                "kind": Dataset.KIND_INPUT,
                "status": "ready",
                "is_system": True,
            },
        )

        dataset.kind = Dataset.KIND_INPUT
        dataset.status = "ready"
        dataset.is_system = True
        dataset.save(update_fields=["kind", "status", "is_system"])

        target_root = dataset_upload_root(user.id, dataset.id)

        if target_root.exists():
            shutil.rmtree(target_root)

        target_root.mkdir(parents=True, exist_ok=True)

        DatasetFile.objects.filter(dataset=dataset).delete()

        for source_path in source_files:
            relative = source_path.relative_to(source_root)
            relative_path = safe_relative_path(relative.as_posix())

            target_path = target_root / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

            DatasetFile.objects.create(
                dataset=dataset,
                relative_path=relative_path.as_posix(),
                size_bytes=target_path.stat().st_size,
            )

        return dataset


def sync_builtin_model_files_dataset_for_all_users() -> int:
    count = 0

    for user in User.objects.filter(is_active=True):
        dataset = sync_builtin_model_files_dataset_for_user(user)
        if dataset is not None:
            count += 1

    return count