from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath

import pydicom
from celery.exceptions import Ignore

from ...datasets.serializers import DatasetSerializer
from ...datasets.services import OutputDatasetFile, get_dataset_file_path
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import CollectSingleCTImagesTaskParameters


def _patient_name_from_relative_path(relative_path: str) -> str | None:
    """
    Extract the patient folder name.

    Expected structure:
        ROOT/PATIENT/.../image.dcm

    Example:
        L3_nested/PATIENT001/study/image.dcm
        -> PATIENT001
    """
    normalized = relative_path.replace("\\", "/")
    parts = PurePosixPath(normalized).parts

    # Root + patient + image are required at minimum.
    if len(parts) < 3:
        return None

    return parts[1]


def _is_ct_dicom(path: Path) -> bool:
    """
    Return True when path contains a DICOM object with Modality == CT.

    stop_before_pixels=True keeps the scan inexpensive even for large images.
    force=True also allows DICOM files without a standard file preamble.
    """
    try:
        ds = pydicom.dcmread(
            path,
            stop_before_pixels=True,
            force=True,
        )
    except Exception:
        return False

    return str(getattr(ds, "Modality", "")).upper() == "CT"


def _output_name(
    patient_name: str,
    index: int,
    count: int,
) -> str:
    """
    Generate patient-based flat output names.

    One image:
        PAT001.dcm

    Multiple images:
        PAT001.dcm
        PAT001_002.dcm
        PAT001_003.dcm
    """
    if count == 1 or index == 1:
        return f"{patient_name}.dcm"

    return f"{patient_name}_{index:03d}.dcm"


def run_collect_single_ct_images_task(
    parameters: dict,
    user_id: str,
    celery_task=None,
) -> dict:
    runtime = TaskRuntime(
        task_key="collectsinglectimages",
        parameters=parameters,
        parameter_model=CollectSingleCTImagesTaskParameters,
        user_id=user_id,
        celery_task=celery_task,
    )

    params = runtime.params
    runtime.mark_running()

    try:
        input_dataset = runtime.get_input_dataset(
            params.input_dataset_id
        )

        total = input_dataset.file_count

        # patient name ->
        # [(original relative path, physical source path), ...]
        ct_by_patient: dict[str, list[tuple[str, Path]]] = defaultdict(list)

        dataset_files = sorted(
            input_dataset.files.all(),
            key=lambda f: f.relative_path,
        )

        for current, dataset_file in enumerate(
            dataset_files,
            start=1,
        ):
            runtime.check_cancelled(
                current=current - 1,
                total=total,
                message=(
                    f"Task cancelled after "
                    f"{current - 1} of {total} files"
                ),
            )

            relative_path = dataset_file.relative_path

            patient_name = _patient_name_from_relative_path(
                relative_path
            )

            # Files directly in the root cannot be assigned to a patient.
            if patient_name is not None:
                source_path = get_dataset_file_path(
                    user_id=runtime.user_id,
                    dataset_id=input_dataset.id,
                    relative_path=relative_path,
                )

                if _is_ct_dicom(source_path):
                    ct_by_patient[patient_name].append(
                        (
                            relative_path,
                            source_path,
                        )
                    )

            runtime.update_progress(
                current=current,
                total=total,
                message=f"Scanning files: {current} / {total}",
            )

        output_files: list[OutputDatasetFile] = []

        # Sort patients and files so output is deterministic.
        for patient_name in sorted(ct_by_patient):
            patient_files = sorted(
                ct_by_patient[patient_name],
                key=lambda item: item[0],
            )

            image_count = len(patient_files)

            for index, (_, source_path) in enumerate(
                patient_files,
                start=1,
            ):
                output_files.append(
                    OutputDatasetFile(
                        relative_path=_output_name(
                            patient_name,
                            index,
                            image_count,
                        ),
                        content=source_path.read_bytes(),
                    )
                )

        if not output_files:
            raise ValueError(
                "No CT DICOM images were found in the input dataset."
            )

        output_dataset = runtime.create_output_dataset(
            name=f"Collected CT images - {input_dataset.name}",
            files=output_files,
        )

        runtime.update_progress(
            current=total,
            total=total,
            message=(
                f"Collected {len(output_files)} CT image(s) "
                f"from {len(ct_by_patient)} patient folder(s)"
            ),
        )

        runtime.mark_finished()

        return {
            "current": total,
            "total": total,
            "message": "Collect single CT images task completed",
            "parameters": params.model_dump(mode="json"),
            "output_datasets": [
                DatasetSerializer(output_dataset).data
            ],
        }

    except Ignore:
        raise

    except Exception:
        runtime.mark_failed()
        raise