import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from rest_framework.exceptions import NotFound, ValidationError

from core.common.dicom import get_pixels_from_dicom_object, is_dicom, load_dicom
from core.common.utils import MUSCLE, SAT, VAT
from core.datasets.services import (
    OutputDatasetFile,
    append_output_files_to_dataset,
    create_empty_output_dataset_for_user_id,
    get_dataset_file_path,
)
from core.models import Dataset, DatasetFile
from core.processing.segmentmusclefatl3.service import numpy_to_nifti_to_output_file


ALLOWED_SEGMENTATION_LABELS = {0, MUSCLE, VAT, SAT}
MANUAL_EDITOR_TASK_KEY = "manual_editor_corrections"


@dataclass(frozen=True)
class ManualEditorCase:
    image_file: DatasetFile
    segmentation_file: DatasetFile | None
    correction_image_file: DatasetFile | None
    correction_segmentation_file: DatasetFile | None


def get_manual_editor_datasets_for_user(user) -> list[Dataset]:
    """
    Candidate datasets for manual editing.

    For now this returns output datasets that contain at least one DICOM and
    at least one segmentation file. This avoids hardcoding a task key.
    """
    datasets = (
        Dataset.objects
        .filter(owner=user, kind=Dataset.KIND_OUTPUT, status__in=["done", "ready"])
        .prefetch_related("files")
        .order_by("-created_at")
    )

    result = []

    for dataset in datasets:
        files = list(dataset.files.all())
        has_dicom = False
        has_segmentation = False

        for dataset_file in files:
            name = Path(dataset_file.relative_path).name.lower()

            if name.endswith((".seg.npy", ".seg.nii", ".seg.nii.gz")):
                has_segmentation = True
                continue

            try:
                path = get_dataset_file_path(user.id, dataset.id, dataset_file.relative_path)
                if is_dicom(path):
                    has_dicom = True
            except Exception:
                pass

            if has_dicom and has_segmentation:
                result.append(dataset)
                break

    return result


def _segmentation_key(relative_path: str) -> str | None:
    """
    Returns the image basename for a segmentation file.

    Example:
      image001.dcm.seg.npy -> image001.dcm
      image001.dcm.seg.nii.gz -> image001.dcm
    """
    name = Path(relative_path).name

    suffixes = [
        ".seg.npy",
        ".seg.nii.gz",
        ".seg.nii",
    ]

    for suffix in suffixes:
        if name.endswith(suffix):
            return name.removesuffix(suffix)

    return None


def _dicom_key(relative_path: str) -> str:
    return Path(relative_path).name


def _prefer_numpy(existing: DatasetFile | None, candidate: DatasetFile) -> DatasetFile:
    """
    Prefer .npy over .nii/.nii.gz when multiple segmentation files exist.
    """
    if existing is None:
        return candidate

    existing_name = existing.relative_path.lower()
    candidate_name = candidate.relative_path.lower()

    if candidate_name.endswith(".npy") and not existing_name.endswith(".npy"):
        return candidate

    return existing


def get_manual_editor_cases(
    source_dataset: Dataset,
    user,
    correction_dataset: Dataset | None = None,
) -> list[ManualEditorCase]:
    automatic_segmentation_by_key: dict[str, DatasetFile] = {}
    dicom_files: list[DatasetFile] = []

    for dataset_file in source_dataset.files.all():
        key = _segmentation_key(dataset_file.relative_path)

        if key is not None:
            automatic_segmentation_by_key[key] = _prefer_numpy(
                automatic_segmentation_by_key.get(key),
                dataset_file,
            )
            continue

        try:
            path = get_dataset_file_path(
                user.id,
                source_dataset.id,
                dataset_file.relative_path,
            )
            if is_dicom(path):
                dicom_files.append(dataset_file)
        except Exception:
            continue

    correction_image_by_key: dict[str, DatasetFile] = {}
    correction_segmentation_by_key: dict[str, DatasetFile] = {}

    if correction_dataset is not None:
        for dataset_file in correction_dataset.files.all():
            key = _segmentation_key(dataset_file.relative_path)

            if key is not None:
                correction_segmentation_by_key[key] = _prefer_numpy(
                    correction_segmentation_by_key.get(key),
                    dataset_file,
                )
                continue

            try:
                path = get_dataset_file_path(
                    user.id,
                    correction_dataset.id,
                    dataset_file.relative_path,
                )
                if is_dicom(path):
                    correction_image_by_key[_dicom_key(dataset_file.relative_path)] = dataset_file
            except Exception:
                continue

    cases = []

    for image_file in dicom_files:
        key = _dicom_key(image_file.relative_path)

        cases.append(
            ManualEditorCase(
                image_file=image_file,
                segmentation_file=automatic_segmentation_by_key.get(key),
                correction_image_file=correction_image_by_key.get(key),
                correction_segmentation_file=correction_segmentation_by_key.get(key),
            )
        )

    return cases


def get_owned_dataset(user, dataset_id) -> Dataset:
    try:
        return Dataset.objects.prefetch_related("files").get(id=dataset_id, owner=user)
    except Dataset.DoesNotExist:
        raise NotFound("Dataset not found")


def get_owned_dataset_file(user, file_id) -> DatasetFile:
    try:
        return DatasetFile.objects.select_related("dataset").get(
            id=file_id,
            dataset__owner=user,
        )
    except DatasetFile.DoesNotExist:
        raise NotFound("Dataset file not found")
    

def manual_correction_dataset_name(source_dataset: Dataset) -> str:
    return f"Manual corrections - {source_dataset.name}"


def get_manual_correction_output_datasets(
    *,
    source_dataset: Dataset,
    user,
) -> list[Dataset]:
    return list(
        Dataset.objects
        .filter(
            owner=user,
            kind=Dataset.KIND_OUTPUT,
            source_task_key=MANUAL_EDITOR_TASK_KEY,
            source_dataset=source_dataset,
        )
        .order_by("-created_at")
    )


def get_manual_correction_output_dataset(
    *,
    source_dataset: Dataset,
    user,
    output_dataset_id=None,
    create_if_missing: bool = False,
) -> Dataset | None:
    """
    Returns the selected/manual correction output dataset.

    If output_dataset_id is provided, that dataset must belong to the user
    and must be linked to the selected source dataset.

    If output_dataset_id is empty, reuse the latest correction dataset for
    this source dataset. If none exists and create_if_missing=True, create one.
    """
    if output_dataset_id:
        try:
            return Dataset.objects.get(
                id=output_dataset_id,
                owner=user,
                kind=Dataset.KIND_OUTPUT,
                source_task_key=MANUAL_EDITOR_TASK_KEY,
                source_dataset=source_dataset,
            )
        except Dataset.DoesNotExist:
            raise NotFound("Manual correction output dataset not found")

    existing = (
        Dataset.objects
        .filter(
            owner=user,
            kind=Dataset.KIND_OUTPUT,
            source_task_key=MANUAL_EDITOR_TASK_KEY,
            source_dataset=source_dataset,
        )
        .order_by("-created_at")
        .first()
    )

    if existing is not None:
        return existing

    if not create_if_missing:
        return None

    return create_empty_output_dataset_for_user_id(
        name=manual_correction_dataset_name(source_dataset),
        user_id=user.id,
        source_task_key=MANUAL_EDITOR_TASK_KEY,
        source_dataset=source_dataset,
        status="done",
    )


def _array_to_base64(array: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(array).tobytes()).decode("ascii")


def _base64_to_array(value: str, *, dtype: np.dtype, shape: tuple[int, int]) -> np.ndarray:
    try:
        raw = base64.b64decode(value)
    except Exception:
        raise ValidationError("Invalid base64 payload")

    array = np.frombuffer(raw, dtype=dtype)

    expected_size = shape[0] * shape[1]

    if array.size != expected_size:
        raise ValidationError(
            f"Invalid mask size. Expected {expected_size} values, received {array.size}."
        )

    return array.reshape(shape)


def _dicom_float(value, default: float) -> float:
    """
    Convert normal DICOM numeric values and pydicom MultiValue values to float.
    Uses the first value when multiple alternatives are present.
    """
    if value is None:
        return default

    try:
        if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
            value = value[0]
    except Exception:
        pass

    try:
        return float(value)
    except Exception:
        return default


def get_image_payload(dataset_file: DatasetFile, user) -> dict[str, Any]:
    path = get_dataset_file_path(
        user.id,
        dataset_file.dataset_id,
        dataset_file.relative_path,
    )

    dicom_object = load_dicom(path)

    if dicom_object is None:
        raise ValidationError("Selected file is not a readable DICOM file")

    image = get_pixels_from_dicom_object(dicom_object, normalize=True).astype(np.float32)

    rows, columns = image.shape

    pixel_spacing = getattr(dicom_object, "PixelSpacing", [1.0, 1.0])
    window_center = getattr(dicom_object, "WindowCenter", 50)
    window_width = getattr(dicom_object, "WindowWidth", 400)

    row_spacing = _dicom_float(pixel_spacing[0], 1.0)
    column_spacing = _dicom_float(pixel_spacing[1], 1.0)
    window_center = _dicom_float(window_center, 50.0)
    window_width = _dicom_float(window_width, 400.0)

    return {
        "file_id": str(dataset_file.id),
        "relative_path": dataset_file.relative_path,
        "rows": int(rows),
        "columns": int(columns),
        "dtype": "float32",
        "spacing": [row_spacing, column_spacing],
        "window_center": window_center,
        "window_width": window_width,
        "pixel_data_base64": _array_to_base64(image),
    }


def _load_segmentation_array(path: Path) -> np.ndarray:
    name = path.name.lower()

    if name.endswith(".npy"):
        segmentation = np.load(path)
    elif name.endswith((".nii", ".nii.gz")):
        import SimpleITK as sitk

        image = sitk.ReadImage(str(path))
        segmentation = sitk.GetArrayFromImage(image)

        if segmentation.ndim == 3 and segmentation.shape[0] == 1:
            segmentation = segmentation[0]
    else:
        raise ValidationError("Unsupported segmentation file type")

    if segmentation.ndim != 2:
        raise ValidationError("Segmentation must be a 2D mask")

    segmentation = segmentation.astype(np.uint8)

    labels = set(np.unique(segmentation).astype(int).tolist())
    unknown_labels = labels - ALLOWED_SEGMENTATION_LABELS

    if unknown_labels:
        raise ValidationError(f"Segmentation contains unknown labels: {sorted(unknown_labels)}")

    return segmentation


def get_segmentation_payload(dataset_file: DatasetFile, user) -> dict[str, Any]:
    path = get_dataset_file_path(
        user.id,
        dataset_file.dataset_id,
        dataset_file.relative_path,
    )

    segmentation = _load_segmentation_array(path)

    rows, columns = segmentation.shape

    return {
        "file_id": str(dataset_file.id),
        "relative_path": dataset_file.relative_path,
        "rows": int(rows),
        "columns": int(columns),
        "dtype": "uint8",
        "labels": {
            "0": "Background",
            str(MUSCLE): "Muscle",
            str(VAT): "Visceral fat",
            str(SAT): "Subcutaneous fat",
        },
        "mask_base64": _array_to_base64(segmentation),
    }


def correction_relative_paths(image_relative_path: str) -> tuple[str, str]:
    """
    Output names inside the manual correction dataset.

    Example:
      image001.dcm
      image001.dcm.seg.npy
    """
    image_name = Path(image_relative_path).name
    return image_name, f"{image_name}.seg.npy"


def save_corrected_segmentation(
    *,
    source_dataset: Dataset,
    image_file: DatasetFile,
    user,
    rows: int,
    columns: int,
    mask_base64: str,
    output_dataset_id=None,
) -> dict[str, Any]:
    mask = _base64_to_array(
        mask_base64,
        dtype=np.uint8,
        shape=(rows, columns),
    )

    labels = set(np.unique(mask).astype(int).tolist())
    unknown_labels = labels - ALLOWED_SEGMENTATION_LABELS

    if unknown_labels:
        raise ValidationError(
            f"Corrected mask contains unknown labels: {sorted(unknown_labels)}"
        )

    output_dataset = get_manual_correction_output_dataset(
        source_dataset=source_dataset,
        user=user,
        output_dataset_id=output_dataset_id,
        create_if_missing=True,
    )

    image_relative_path, segmentation_relative_path = correction_relative_paths(
        image_file.relative_path
    )

    source_image_path = get_dataset_file_path(
        user.id,
        image_file.dataset_id,
        image_file.relative_path,
    )

    from io import BytesIO

    buffer = BytesIO()
    np.save(buffer, mask)

    output_files = [
        OutputDatasetFile(
            relative_path=image_relative_path,
            content=source_image_path.read_bytes(),
        ),
        OutputDatasetFile(
            relative_path=segmentation_relative_path,
            content=buffer.getvalue(),
        ),
    ]

    append_output_files_to_dataset(output_dataset, output_files)

    output_image_file = DatasetFile.objects.get(
        dataset=output_dataset,
        relative_path=image_relative_path,
    )

    output_segmentation_file = DatasetFile.objects.get(
        dataset=output_dataset,
        relative_path=segmentation_relative_path,
    )

    return {
        "output_dataset_id": str(output_dataset.id),
        "output_dataset_name": output_dataset.name,
        "output_image_file_id": str(output_image_file.id),
        "output_image_relative_path": output_image_file.relative_path,
        "output_segmentation_file_id": str(output_segmentation_file.id),
        "output_segmentation_relative_path": output_segmentation_file.relative_path,
    }