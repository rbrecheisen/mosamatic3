"""Mosamatic2-compatible T4 PyTorch body-composition segmentation task.

The T4 ``.pt`` files contain PyTorch state_dict weights rather than self-contained
TorchScript modules.  The original Mosamatic2 UNet architecture is therefore
reconstructed from ``models.py`` before loading the weights.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import torch
from celery.exceptions import Ignore

from ...common.dicom import get_pixels_from_dicom_object, is_dicom, load_dicom
from ...common.utils import convert_labels_to_157, normalize_between
from ...datasets.serializers import DatasetSerializer
from ...datasets.services import OutputDatasetFile, get_dataset_file_path
from ...models import Dataset
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import SegmentMuscleFatT4PyTorchTaskParameters
from . import models
from .paramloader import ParamLoader


DEVICE = "cpu"


def find_t4_model_files(model_dataset: Dataset, user_id: str, model_version: str) -> tuple[Path, Path, Path]:
    """Locate the same three model files expected by Mosamatic2."""
    expected = {
        "model": f"model-{model_version}.pt",
        "contour": f"contour_model-{model_version}.pt",
        "params": f"params-{model_version}.json",
    }
    found: dict[str, list[Path]] = {key: [] for key in expected}

    for entry in model_dataset.files.all():
        name = Path(entry.relative_path).name
        for key, expected_name in expected.items():
            if name == expected_name:
                found[key].append(
                    get_dataset_file_path(user_id, model_dataset.id, entry.relative_path)
                )

    missing = [expected[key] for key, paths in found.items() if not paths]
    duplicates = [expected[key] for key, paths in found.items() if len(paths) > 1]
    if missing or duplicates:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if duplicates:
            details.append(f"multiple matches: {', '.join(duplicates)}")
        raise RuntimeError(
            f"T4 model dataset '{model_dataset.name}' must contain exactly one each of "
            f"{expected['model']}, {expected['contour']} and {expected['params']} "
            f"({'; '.join(details)})."
        )

    return found["model"][0], found["contour"][0], found["params"][0]


def load_t4_models_and_params(
    model_dataset: Dataset,
    user_id: str,
    model_version: str,
):
    """Reconstruct Mosamatic2 UNets and load their state_dict weights."""
    model_path, contour_model_path, params_path = find_t4_model_files(
        model_dataset, user_id, model_version
    )

    # Load params first: models.UNet reads params.dict['dropout_rate'].
    params = ParamLoader(params_path)
    for required_key in ("dropout_rate", "lower_bound", "upper_bound"):
        if required_key not in params.dict:
            raise ValueError(
                f"{params_path.name} is missing required T4 parameter '{required_key}'"
            )

    device = torch.device(DEVICE)

    # Mosamatic2 uses the same UNet architecture with four body-composition
    # classes and two contour classes.
    model = models.UNet(params, 4).to(device=device)
    model.load_state_dict(
        torch.load(model_path, weights_only=False, map_location=device)
    )
    model.eval()

    contour_model = models.UNet(params, 2).to(device=device)
    contour_model.load_state_dict(
        torch.load(contour_model_path, weights_only=False, map_location=device)
    )
    contour_model.eval()

    return model, contour_model, params


def extract_contour(image: np.ndarray, contour_model) -> np.ndarray:
    """Apply the Mosamatic2 two-class contour model and mask the input image."""
    with torch.no_grad():
        tensor = np.expand_dims(image, 0)
        tensor = np.expand_dims(tensor, 0)
        tensor = torch.Tensor(tensor)
        tensor = tensor.to(DEVICE, dtype=torch.float)

        prediction = contour_model(tensor)
        prediction = torch.argmax(prediction, axis=1)
        prediction = prediction.squeeze()
        prediction = prediction.detach().cpu().numpy()

        return image * prediction


def segment_muscle_and_fat(
    image: np.ndarray,
    model,
    *,
    probabilities: bool = False,
) -> np.ndarray:
    """Run the four-class Mosamatic2 T4 UNet."""
    tensor = np.expand_dims(image, 0)
    tensor = np.expand_dims(tensor, 0)
    tensor = torch.Tensor(tensor)
    tensor = tensor.to(DEVICE, dtype=torch.float)

    with torch.no_grad():
        prediction = model(tensor)

    if probabilities:
        # The original UNet already returns softmax probabilities as NCHW.
        return (
            prediction.squeeze(0)
            .permute(1, 2, 0)
            .detach()
            .cpu()
            .numpy()
            .astype(np.float32)
        )

    segmentation = torch.argmax(prediction, axis=1)
    segmentation = segmentation.squeeze()
    return segmentation.detach().cpu().numpy()


def numpy_to_output_file(relative_path: str, array: np.ndarray) -> OutputDatasetFile:
    with BytesIO() as buffer:
        np.save(buffer, array)
        return OutputDatasetFile(relative_path=relative_path, content=buffer.getvalue())


def process_dicom_file(
    *,
    dicom_path: Path,
    relative_path: str,
    model,
    contour_model,
    params: ParamLoader,
    probabilities: bool,
) -> list[OutputDatasetFile]:
    """Mirror Mosamatic2 preprocessing/inference while producing Mosamatic3 output."""
    dicom_object = load_dicom(dicom_path)
    if dicom_object is None:
        raise RuntimeError(f"Could not read T4 DICOM: {relative_path}")

    # Mosamatic2 requests normalized=True here, which means conversion back to HU
    # using DICOM RescaleSlope/RescaleIntercept.
    pixels = get_pixels_from_dicom_object(dicom_object, normalize=True)

    # Exact Mosamatic2 preprocessing: normalize using lower_bound/upper_bound,
    # then multiply by the binary contour prediction before the 4-class model.
    pixels = normalize_between(
        pixels,
        params.dict["lower_bound"],
        params.dict["upper_bound"],
    )
    pixels = extract_contour(pixels, contour_model)
    pixels = pixels.astype(np.float32)

    segmentation = segment_muscle_and_fat(
        pixels,
        model,
        probabilities=probabilities,
    )

    source_path = Path(relative_path)
    source_name = source_path.name
    safe_prefix = "_".join(source_path.parts[:-1]).replace(" ", "_")
    flat_name = f"{safe_prefix}_{source_name}" if safe_prefix else source_name

    if probabilities:
        segmentation_relative_path = f"{flat_name}_prob.seg.npy"
    else:
        # Mosamatic2 maps model class IDs 0/1/2/3 to application labels 0/1/5/7.
        segmentation = convert_labels_to_157(segmentation)
        if segmentation.shape != pixels.shape:
            raise RuntimeError(
                f"T4 segmentation shape {segmentation.shape} does not match "
                f"input image shape {pixels.shape} for {relative_path}"
            )
        segmentation_relative_path = f"{flat_name}.seg.npy"

    # Unlike the desktop task, Mosamatic3 also carries the DICOM forward because
    # Calculate Scores expects DICOM + .seg.npy in the same output dataset.
    return [
        numpy_to_output_file(segmentation_relative_path, segmentation),
        OutputDatasetFile(relative_path=flat_name, content=dicom_path.read_bytes()),
    ]


def normalize_path_prefix(prefix: str | None) -> str:
    value = (prefix or "").strip().replace("\\", "/").strip("/")
    return f"{value}/" if value else ""


def get_t4_input_dataset_files(
    dataset: Dataset,
    user_id: str,
    input_path_prefix: str | None,
):
    prefix = normalize_path_prefix(input_path_prefix)
    result = []
    for entry in dataset.files.all():
        relative_path = entry.relative_path.replace("\\", "/")
        if prefix and not relative_path.startswith(prefix):
            continue
        path = get_dataset_file_path(user_id, dataset.id, entry.relative_path)
        if is_dicom(path):
            result.append(entry)
    return result


def run_segment_muscle_fat_t4_pytorch_task(
    parameters: dict,
    user_id: str,
    celery_task=None,
) -> dict:
    runtime = TaskRuntime(
        task_key="segmentmusclefatt4pytorch",
        parameters=parameters,
        parameter_model=SegmentMuscleFatT4PyTorchTaskParameters,
        user_id=user_id,
        celery_task=celery_task,
    )
    params = runtime.params
    runtime.mark_running()

    try:
        image_dataset = runtime.get_input_dataset(params.dataset_id)
        model_dataset = runtime.get_input_dataset(params.model_files_dataset_id)

        input_files = get_t4_input_dataset_files(
            image_dataset,
            user_id,
            params.input_path_prefix,
        )
        if not input_files:
            raise RuntimeError("No T4 DICOM images found in the input dataset")

        total = len(input_files)
        runtime.update_progress(
            current=0,
            total=total,
            message="Loading T4 PyTorch models",
        )

        model, contour_model, model_params = load_t4_models_and_params(
            model_dataset,
            user_id,
            params.model_version,
        )

        output_files: list[OutputDatasetFile] = []
        for index, entry in enumerate(input_files):
            runtime.check_cancelled(
                current=index,
                total=total,
                message=f"T4 segmentation cancelled after {index} of {total} files",
            )

            image_path = get_dataset_file_path(
                user_id,
                image_dataset.id,
                entry.relative_path,
            )
            output_files.extend(
                process_dicom_file(
                    dicom_path=image_path,
                    relative_path=entry.relative_path,
                    model=model,
                    contour_model=contour_model,
                    params=model_params,
                    probabilities=params.probabilities,
                )
            )
            runtime.update_progress(
                current=index + 1,
                total=total,
                message=f"Segmented T4 DICOM file {index + 1} of {total}",
            )

        output_dataset = runtime.create_output_dataset(
            name=f"Segment Muscle/Fat T4 PyTorch output - {image_dataset.name}",
            files=output_files,
        )

        runtime.mark_finished()
        return {
            "current": total,
            "total": total,
            "message": "Segment muscle/fat T4 PyTorch task completed",
            "parameters": params.model_dump(mode="json"),
            "output_datasets": [DatasetSerializer(output_dataset).data],
            "output_dataset_id": str(output_dataset.id),
        }

    except Ignore:
        raise
    except Exception:
        runtime.mark_failed()
        raise
