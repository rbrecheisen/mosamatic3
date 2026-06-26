import csv
from io import BytesIO
from pathlib import Path
from typing import Literal
import tempfile
import time

import numpy as np
import pandas as pd
from celery.exceptions import Ignore

from ...common.dicom import (
    is_dicom,
    load_dicom,
    get_pixels_from_dicom_object,
)
from ...common.utils import (
    get_pixels_from_tag_file,
    calculate_area,
    calculate_index,
    calculate_bmi,
    calculate_sarcopenia,
    calculate_sarcopenic_obesity,
    calculate_myosteatosis,
    calculate_visceral_obesity,
    calculate_mean_radiation_attenuation,
    calculate_lama_percentage,
    apply_window_center_and_width,
    convert_numpy_array_to_png_image,
    AlbertaColorMap,
    MUSCLE,
    VAT,
    SAT,
)
from ...datasets.serializers import DatasetSerializer
from ...datasets.services import OutputDatasetFile, get_dataset_file_path
from ...models import Dataset
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import CalculateScoresTaskParameters


PatientInfo = list[dict[str, str]]


def normalize_path_prefix(prefix: str | None) -> str:
    value = (prefix or '').strip().replace('\\', '/').strip('/')
    return f'{value}/' if value else ''


def flat_name_from_relative_path(relative_path: str) -> str:
    source_path = Path(relative_path)
    source_name = source_path.name
    safe_prefix = "_".join(source_path.parts[:-1]).replace(" ", "_")
    return f"{safe_prefix}_{source_name}" if safe_prefix else source_name


def safe_png_name(relative_path: str, suffix: str) -> str:
    """
    Creates a flat, safe PNG filename.

    Example:
        patient1/image001.dcm + dicom
        -> patient1_image001.dcm.dicom.png
    """
    path = Path(relative_path)
    safe_prefix = "_".join(path.parts[:-1]).replace(" ", "_")
    base_name = path.name.replace(" ", "_")

    if safe_prefix:
        base_name = f"{safe_prefix}_{base_name}"

    return f"{base_name}.{suffix}.png"


def collect_dicom_files(
    dataset: Dataset,
    user_id: str,
    input_path_prefix: str | None,
) -> list:
    prefix = normalize_path_prefix(input_path_prefix)
    result = []

    for dataset_file in dataset.files.all():
        relative_path = dataset_file.relative_path.replace('\\', '/')

        if prefix and not relative_path.startswith(prefix):
            continue

        path = get_dataset_file_path(user_id, dataset.id, dataset_file.relative_path)

        if is_dicom(path):
            result.append(dataset_file)

    return result


def collect_segmentation_files(
    dataset: Dataset,
    user_id: str,
    file_type: Literal['npy', 'nifti', 'tag'],
    input_path_prefix: str | None,
) -> dict[str, object]:
    prefix = normalize_path_prefix(input_path_prefix)
    result = {}

    for dataset_file in dataset.files.all():
        relative_path = dataset_file.relative_path.replace('\\', '/')

        if prefix and not relative_path.startswith(prefix):
            continue

        name = Path(relative_path).name

        if file_type == 'npy':
            if not name.endswith('.seg.npy'):
                continue
            key = name.removesuffix('.seg.npy')

        elif file_type == 'nifti':
            if name.endswith('.seg.nii.gz'):
                key = name.removesuffix('.seg.nii.gz')
            elif name.endswith('.seg.nii'):
                key = name.removesuffix('.seg.nii')
            else:
                continue

        elif file_type == 'tag':
            if not name.endswith('.tag'):
                continue
            key = name.removesuffix('.tag').removesuffix('.dcm')

        else:
            raise RuntimeError(f'Unknown segmentation file type: {file_type}')

        result[key] = dataset_file

    return result


def collect_img_seg_pairs(
    *,
    image_dataset: Dataset,
    segmentation_dataset: Dataset,
    user_id: str,
    file_type: Literal['npy', 'nifti', 'tag'],
    image_path_prefix: str | None,
    segmentation_path_prefix: str | None,
) -> list[tuple[object, object]]:
    dicom_files = collect_dicom_files(
        image_dataset,
        user_id,
        image_path_prefix,
    )

    segmentation_files_by_key = collect_segmentation_files(
        segmentation_dataset,
        user_id,
        file_type,
        segmentation_path_prefix,
    )

    pairs = []

    for dicom_file in dicom_files:
        relative_path = dicom_file.relative_path
        dicom_name = Path(relative_path).name

        key_candidates = [
            dicom_name,
            dicom_name.removesuffix('.dcm'),
        ]

        flat_name = flat_name_from_relative_path(relative_path)
        key_candidates.extend([
            flat_name,
            flat_name.removesuffix('.dcm'),
        ])

        for key in key_candidates:
            segmentation_file = segmentation_files_by_key.get(key)

            if segmentation_file is not None:
                pairs.append((dicom_file, segmentation_file))
                break

    return pairs


def validate_segmentation_labels(segmentation: np.ndarray, path: Path) -> np.ndarray:
    if segmentation.ndim != 2:
        raise RuntimeError(f'Segmentation must be 2D: {path.name}')

    labels = set(np.unique(segmentation).astype(int).tolist())
    allowed_labels = {0, MUSCLE, VAT, SAT}
    unknown_labels = labels - allowed_labels

    if unknown_labels:
        raise RuntimeError(
            f'Segmentation {path.name} contains unknown labels: {sorted(unknown_labels)}'
        )

    return segmentation


def load_segmentation(path: Path, file_type: Literal['npy', 'nifti', 'tag']) -> np.ndarray | None:
    if file_type == 'npy':
        segmentation = np.load(path)
        return validate_segmentation_labels(segmentation, path)

    if file_type == 'nifti':
        import SimpleITK as sitk

        image = sitk.ReadImage(str(path))
        segmentation = sitk.GetArrayFromImage(image)

        # SimpleITK returns arrays as z, y, x.
        # Your segment task writes 2D masks as a single-slice 3D volume: 1, y, x.
        if segmentation.ndim == 3 and segmentation.shape[0] == 1:
            segmentation = segmentation[0]

        segmentation = segmentation.astype(np.int16)
        return validate_segmentation_labels(segmentation, path)

    if file_type == 'tag':
        pixels = get_pixels_from_tag_file(path)
        try:
            return pixels.reshape(512, 512)
        except Exception:
            return None

    raise RuntimeError(f'Unknown segmentation file type: {file_type}')


def load_patient_info(path: Path) -> PatientInfo:
    required_columns = {'file', 'height', 'weight', 'sex', 'age'}

    with path.open(mode='r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise RuntimeError('Patient info CSV has no header row')

        missing = required_columns - set(reader.fieldnames)

        if missing:
            raise RuntimeError(
                f'Patient info CSV misses required columns: {", ".join(sorted(missing))}'
            )

        return [row for row in reader]


def find_patient_info_file(dataset: Dataset, user_id: str, relative_path: str | None) -> Path | None:
    if not relative_path:
        csv_files = [
            dataset_file
            for dataset_file in dataset.files.all()
            if dataset_file.relative_path.lower().endswith('.csv')
        ]

        if len(csv_files) == 0:
            return None

        if len(csv_files) > 1:
            raise RuntimeError(
                'Patient info dataset contains multiple CSV files. '
                'Set patient_info_relative_path explicitly.'
            )

        relative_path = csv_files[0].relative_path

    return get_dataset_file_path(user_id, dataset.id, relative_path)


def find_patient_row(file_name: str, patient_info: PatientInfo | None) -> dict[str, str] | None:
    if not patient_info:
        return None

    for row in patient_info:
        if row['file'] in file_name:
            return row

    return None


def optional_float(row: dict[str, str] | None, key: str) -> float | None:
    if row is None:
        return None

    value = row.get(key)

    if value in (None, ''):
        return None

    return float(value)


def optional_sex(row: dict[str, str] | None) -> str:
    if row is None:
        return 'unknown'

    sex = str(row.get('sex', '')).strip().lower()

    if sex in {'male', 'female'}:
        return sex

    return 'unknown'


def dataframe_to_csv_output_file(df: pd.DataFrame, relative_path: str) -> OutputDatasetFile:
    buffer = BytesIO()
    df.to_csv(buffer, index=False, sep=';')
    return OutputDatasetFile(relative_path=relative_path, content=buffer.getvalue())


def dataframe_to_excel_output_file(df: pd.DataFrame, relative_path: str) -> OutputDatasetFile:
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    return OutputDatasetFile(relative_path=relative_path, content=buffer.getvalue())


def file_to_output_file(source_path: Path, relative_path: str) -> OutputDatasetFile:
    return OutputDatasetFile(
        relative_path=relative_path,
        content=source_path.read_bytes(),
    )


def create_dicom_png_output_file(
    *,
    image: np.ndarray,
    output_dir: Path,
    dicom_relative_path: str,
    window_level: int = 50,
    window_width: int = 400,
) -> OutputDatasetFile:
    png_name = safe_png_name(dicom_relative_path, 'dicom')
    png_path = output_dir / png_name

    image_png = apply_window_center_and_width(
        image,
        center=window_level,
        width=window_width,
    )

    convert_numpy_array_to_png_image(
        image_png,
        str(output_dir),
        color_map=None,
        png_file_name=png_name,
    )

    return file_to_output_file(
        source_path=png_path,
        relative_path=f'{png_name}',
    )


def create_segmentation_png_output_file(
    *,
    segmentation: np.ndarray,
    output_dir: Path,
    segmentation_relative_path: str,
) -> OutputDatasetFile:
    png_name = safe_png_name(segmentation_relative_path, 'segmentation')
    png_path = output_dir / png_name

    segmentation_uint8 = segmentation.astype(np.uint8)

    convert_numpy_array_to_png_image(
        segmentation_uint8,
        str(output_dir),
        color_map=AlbertaColorMap(),
        png_file_name=png_name,
    )

    return file_to_output_file(
        source_path=png_path,
        relative_path=f'{png_name}',
    )


def run_calculate_scores_task(parameters: dict, user_id: str, celery_task=None) -> dict:
    runtime = TaskRuntime(
        task_key='calculatescores',
        parameters=parameters,
        parameter_model=CalculateScoresTaskParameters,
        user_id=user_id,
        celery_task=celery_task,
    )

    params = runtime.params
    runtime.mark_running()

    try:
        input_dataset = runtime.get_input_dataset(params.input_dataset_id)

        patient_info = None

        if params.patient_info_dataset_id:
            patient_info_dataset = runtime.get_input_dataset(params.patient_info_dataset_id)
            patient_info_path = find_patient_info_file(
                patient_info_dataset,
                user_id,
                params.patient_info_relative_path,
            )

            if patient_info_path is not None:
                patient_info = load_patient_info(patient_info_path)

        pairs = collect_img_seg_pairs(
            image_dataset=input_dataset,
            segmentation_dataset=input_dataset,
            user_id=user_id,
            file_type=params.file_type,
            image_path_prefix=params.input_path_prefix,
            segmentation_path_prefix=params.input_path_prefix,
        )

        total = len(pairs)

        if total == 0:
            raise RuntimeError(
                'No matching DICOM/segmentation pairs found. '
                'Check whether the segmentation filenames match the DICOM filenames.'
            )

        runtime.update_progress(
            current=0,
            total=total,
            message=f'Starting score calculation for {total} DICOM/segmentation pairs',
        )

        data = {
            'file': [],
            'muscle_area': [],
            'muscle_idx': [],
            'muscle_ra': [],
            'muscle_lama_perc': [],
            'vat_area': [],
            'vat_idx': [],
            'vat_ra': [],
            'sat_area': [],
            'sat_idx': [],
            'sat_ra': [],
            'bmi': [],
            'sarcopenia': [],
            'sarcopenic_obesity': [],
            'myosteatosis': [],
            'visceral_obesity': [],
        }

        output_files: list[OutputDatasetFile] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            png_output_dir = Path(temp_dir)

            for index, (dicom_file, segmentation_file) in enumerate(pairs):
                current = index + 1

                runtime.check_cancelled(
                    current=index,
                    total=total,
                    message=f'Calculate scores task cancelled after {index} of {total} files',
                )

                dicom_path = get_dataset_file_path(
                    user_id,
                    input_dataset.id,
                    dicom_file.relative_path,
                )

                segmentation_path = get_dataset_file_path(
                    user_id,
                    input_dataset.id,
                    segmentation_file.relative_path,
                )

                dicom_object = load_dicom(dicom_path)

                if dicom_object is None:
                    raise RuntimeError(f'Could not load DICOM image: {dicom_file.relative_path}')

                image = get_pixels_from_dicom_object(dicom_object, normalize=True)
                pixel_spacing = dicom_object.PixelSpacing

                segmentation = load_segmentation(segmentation_path, params.file_type)

                if segmentation is None:
                    raise RuntimeError(f'Could not load segmentation: {segmentation_file.relative_path}')

                output_files.append(
                    create_dicom_png_output_file(
                        image=image,
                        output_dir=png_output_dir,
                        dicom_relative_path=dicom_file.relative_path,
                    )
                )

                output_files.append(
                    create_segmentation_png_output_file(
                        segmentation=segmentation,
                        output_dir=png_output_dir,
                        segmentation_relative_path=segmentation_file.relative_path,
                    )
                )

                file_name = Path(dicom_file.relative_path).name
                patient_row = find_patient_row(file_name, patient_info)

                height = optional_float(patient_row, 'height')
                weight = optional_float(patient_row, 'weight')
                sex = optional_sex(patient_row)

                muscle_area = calculate_area(segmentation, MUSCLE, pixel_spacing)
                muscle_idx = calculate_index(muscle_area, height) if height else 0
                muscle_ra = calculate_mean_radiation_attenuation(image, segmentation, MUSCLE)
                muscle_lama_perc = calculate_lama_percentage(image, segmentation, MUSCLE)

                vat_area = calculate_area(segmentation, VAT, pixel_spacing)
                vat_idx = calculate_index(vat_area, height) if height else 0
                vat_ra = calculate_mean_radiation_attenuation(image, segmentation, VAT)

                sat_area = calculate_area(segmentation, SAT, pixel_spacing)
                sat_idx = calculate_index(sat_area, height) if height else 0
                sat_ra = calculate_mean_radiation_attenuation(image, segmentation, SAT)

                bmi = calculate_bmi(weight, height) if weight and height else 0

                sarcopenia = calculate_sarcopenia(muscle_idx, bmi, sex) if patient_row else 'unknown'
                sarcopenic_obesity = calculate_sarcopenic_obesity(muscle_idx, bmi, sex) if patient_row else 'unknown'
                myosteatosis = calculate_myosteatosis(muscle_ra, bmi) if patient_row else 'unknown'
                visceral_obesity = calculate_visceral_obesity(vat_area)

                data['file'].append(file_name)
                data['muscle_area'].append(muscle_area)
                data['muscle_idx'].append(muscle_idx)
                data['muscle_ra'].append(muscle_ra)
                data['muscle_lama_perc'].append(muscle_lama_perc)
                data['vat_area'].append(vat_area)
                data['vat_idx'].append(vat_idx)
                data['vat_ra'].append(vat_ra)
                data['sat_area'].append(sat_area)
                data['sat_idx'].append(sat_idx)
                data['sat_ra'].append(sat_ra)
                data['bmi'].append(bmi)
                data['sarcopenia'].append(sarcopenia)
                data['sarcopenic_obesity'].append(sarcopenic_obesity)
                data['myosteatosis'].append(myosteatosis)
                data['visceral_obesity'].append(visceral_obesity)

                runtime.update_progress(
                    current=current,
                    total=total,
                    message=f'Calculated scores and PNGs for file {current} of {total}',
                )

                time.sleep(0.01)

        df = pd.DataFrame(data=data)

        output_files.insert(0, dataframe_to_excel_output_file(df, 'bc_scores.xlsx'))
        output_files.insert(0, dataframe_to_csv_output_file(df, 'bc_scores.csv'))

        output_dataset = runtime.create_output_dataset(
            name=f'Calculate Scores output - {input_dataset.name}',
            files=output_files,
        )

        runtime.update_progress(
            current=total,
            total=total,
            message='Finished score calculation',
        )
        runtime.mark_finished()

        return {
            'current': total,
            'total': total,
            'message': 'Calculate scores task completed',
            'parameters': params.model_dump(mode='json'),
            'output_datasets': [DatasetSerializer(output_dataset).data],
            'output_dataset_id': str(output_dataset.id),
        }

    except Ignore:
        raise

    except Exception:
        runtime.mark_failed()
        raise