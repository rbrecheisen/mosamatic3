"""T4 PyTorch/TorchScript segmentation task, compatible with the L3 scoring interface."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import numpy as np
from celery.exceptions import Ignore

from ...common.dicom import get_pixels_from_dicom_object, is_dicom, load_dicom
from ...datasets.serializers import DatasetSerializer
from ...datasets.services import OutputDatasetFile, get_dataset_file_path
from ...models import Dataset
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import SegmentMuscleFatT4PyTorchTaskParameters
from .torch_model import MODEL_EXTENSIONS, load_torchscript_model, map_labels, normalize_ct, predict_t4


def find_t4_files(model_dataset: Dataset, user_id: str, version: str):
    model_names = {f"model-{version}{extension}" for extension in MODEL_EXTENSIONS}
    contour_names = {f"contour_model-{version}{extension}" for extension in MODEL_EXTENSIONS}
    params_name = f"params-{version}.json"
    models, contours, params = [], [], []
    for entry in model_dataset.files.all():
        name = Path(entry.relative_path).name
        path = get_dataset_file_path(user_id, model_dataset.id, entry.relative_path)
        if name in model_names:
            models.append(path)
        elif name in contour_names:
            contours.append(path)
        elif name == params_name:
            params.append(path)
    if len(models) != 1 or len(params) != 1 or len(contours) > 1:
        raise RuntimeError(
            f"T4 model dataset '{model_dataset.name}' must contain exactly one "
            f"model-{version}.pt/.pth/.ts/.zip and one {params_name} "
            f"(optional contour_model-{version}.*). "
            f"Found {len(models)} model(s), {len(params)} params file(s), "
            f"{len(contours)} contour model(s)."
        )
    return models[0], (contours[0] if contours else None), params[0]


def load_t4_models_and_params(model_dataset: Dataset, user_id: str, version: str):
    model_path, contour_path, params_path = find_t4_files(model_dataset, user_id, version)
    config = json.loads(params_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{params_path.name} must contain a JSON object")
    required = ('normalization', 'input_layout', 'output_layout', 'class_labels')
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(
            f"{params_path.name} must explicitly define {', '.join(missing)} "
            "to prevent incorrect T4 preprocessing or tissue-label interpretation. "
            "See segmentmusclefatt4/README.md."
        )
    model = load_torchscript_model(model_path)
    contour = load_torchscript_model(contour_path) if contour_path is not None else None
    if contour is not None and ("min_bound_contour" not in config or "max_bound_contour" not in config):
        raise ValueError("T4 contour model needs min_bound_contour and max_bound_contour in params JSON")
    return model, contour, config


def to_npy(relative_path: str, array: np.ndarray) -> OutputDatasetFile:
    with BytesIO() as buffer:
        np.save(buffer, array)
        return OutputDatasetFile(relative_path=relative_path, content=buffer.getvalue())


def process_dicom_file(*, path: Path, relative_path: str, model, contour_model, config: dict,
                       probabilities: bool) -> list[OutputDatasetFile]:
    dicom = load_dicom(path)
    if dicom is None:
        raise RuntimeError(f"Could not read T4 DICOM: {relative_path}")
    pixels = get_pixels_from_dicom_object(dicom)
    image = normalize_ct(pixels, config)

    if contour_model is not None:
        contour_config = dict(config)
        contour_config.update(
            min_bound=config["min_bound_contour"],
            max_bound=config["max_bound_contour"],
        )
        contour_input = normalize_ct(pixels, contour_config)
        contour_classes = predict_t4(
            contour_input, contour_model, config,
            probabilities=False, enforce_class_count=False,
        )
        image = image * (contour_classes != 0)

    segmentation = predict_t4(image, model, config, probabilities=probabilities)
    source = Path(relative_path)
    safe_prefix = "_".join(source.parts[:-1]).replace(" ", "_")
    flat_name = f"{safe_prefix}_{source.name}" if safe_prefix else source.name
    if probabilities:
        seg_name = f"{flat_name}_prob.seg.npy"
    else:
        segmentation = map_labels(segmentation, config)
        if segmentation.shape != pixels.shape:
            raise RuntimeError(f"T4 segmentation shape mismatch for {relative_path}")
        seg_name = f"{flat_name}.seg.npy"
    return [
        to_npy(seg_name, segmentation),
        OutputDatasetFile(relative_path=flat_name, content=path.read_bytes()),
    ]


def run_segment_muscle_fat_t4_pytorch_task(parameters: dict, user_id: str, celery_task=None) -> dict:
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
        runtime.update_progress(current=0, total=image_dataset.files.count(), message="Loading T4 PyTorch model")
        model, contour_model, model_config = load_t4_models_and_params(
            model_dataset, user_id, params.model_version
        )
        prefix = (params.input_path_prefix or "").strip().replace("\\", "/").strip("/")
        prefix = f"{prefix}/" if prefix else ""
        input_files = []
        for entry in image_dataset.files.all():
            if prefix and not entry.relative_path.replace("\\", "/").startswith(prefix):
                continue
            image_path = get_dataset_file_path(user_id, image_dataset.id, entry.relative_path)
            if is_dicom(image_path):
                input_files.append(entry)
        if not input_files:
            raise RuntimeError("No T4 DICOM images found in the input dataset")

        total = len(input_files)
        output_files = []
        for index, entry in enumerate(input_files):
            runtime.check_cancelled(
                current=index, total=total,
                message=f"T4 segmentation cancelled after {index} of {total} files",
            )
            image_path = get_dataset_file_path(user_id, image_dataset.id, entry.relative_path)
            output_files.extend(process_dicom_file(
                path=image_path,
                relative_path=entry.relative_path,
                model=model,
                contour_model=contour_model,
                config=model_config,
                probabilities=params.probabilities,
            ))
            runtime.update_progress(
                current=index + 1, total=total,
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
