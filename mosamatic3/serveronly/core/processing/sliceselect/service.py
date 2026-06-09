import json
import math
import shutil
import tempfile
import time
import numpy as np
import pydicom
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any
from PIL import Image
from celery.exceptions import Ignore

from ...common.dicom import load_dicom
from ...datasets.serializers import DatasetSerializer
from ...datasets.services import OutputDatasetFile, get_dataset_file_path
from ...models import Dataset
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import SliceSelectTaskParameters


@dataclass
class CandidateScan:
    series_instance_uid: str
    path: Path
    relative_path: str
    description: str = ''
    rows: int = -1
    columns: int = -1
    files: list[Path] = field(default_factory=list)
    relative_files: list[str] = field(default_factory=list)

fast_mode = True
create_review_pngs = True
patient_id_path_part_index = 1


def read_dicom_header(file_path: Path):
    try:
        return pydicom.dcmread(str(file_path), force=True, stop_before_pixels=True)
    except Exception:
        return None


def clean_filename_part(value: str, fallback: str) -> str:
    text = str(value or '').strip() or fallback
    keep = []
    for char in text:
        keep.append(char if char.isalnum() or char in ('-', '_', '.') else '_')
    cleaned = ''.join(keep).strip('._')
    return cleaned or fallback


def patient_id_from_relative_path(relative_path: str, part_index: int, fallback: str) -> str:
    parts = Path(relative_path).parts
    directory_parts = parts[:-1]
    if directory_parts and 0 <= part_index < len(directory_parts):
        return clean_filename_part(directory_parts[part_index], fallback)
    if directory_parts:
        return clean_filename_part(directory_parts[0], fallback)
    return clean_filename_part(fallback, 'unknown_patient')


def find_candidate_scans(dataset: Dataset, user_id: str) -> dict[str, CandidateScan]:
    scans: dict[str, CandidateScan] = {}

    for dataset_file in dataset.files.all():
        file_path = get_dataset_file_path(user_id, dataset.id, dataset_file.relative_path)
        header = read_dicom_header(file_path)
        if header is None:
            continue

        series_uid = getattr(header, 'SeriesInstanceUID', None)
        if not series_uid:
            continue

        series_uid = str(series_uid)
        if series_uid not in scans:
            scans[series_uid] = CandidateScan(
                series_instance_uid=series_uid,
                path=file_path.parent,
                relative_path=str(Path(dataset_file.relative_path).parent),
                description=str(getattr(header, 'SeriesDescription', '') or ''),
                rows=int(getattr(header, 'Rows', -1) or -1),
                columns=int(getattr(header, 'Columns', -1) or -1),
            )

        scans[series_uid].files.append(file_path)
        scans[series_uid].relative_files.append(dataset_file.relative_path)

    return scans


def run_totalsegmentator(scan_dir: Path, output_dir: Path, *, fast: bool) -> None:
    from totalsegmentator.python_api import totalsegmentator

    totalsegmentator(input=str(scan_dir), output=str(output_dir), fast=fast)


def find_selected_slice(scan: CandidateScan, vertebral_level: str, mask_dir: Path) -> tuple[Path | None, float | None, list[str]]:
    import nibabel as nib

    errors = []
    z_positions: dict[float, Path] = {}

    for file_path in scan.files:
        try:
            header = read_dicom_header(file_path)
            if header is not None and hasattr(header, 'ImagePositionPatient'):
                z_positions[float(header.ImagePositionPatient[2])] = file_path
        except Exception as exc:
            errors.append(f'{scan.relative_path}: failed to read z-position from {file_path.name}: {exc}')

    if not z_positions:
        return None, None, [f'{scan.relative_path}: no valid DICOM z-positions found']

    mask_file = mask_dir / f'vertebrae_{vertebral_level}.nii.gz'
    if not mask_file.exists():
        return None, None, [f'{scan.relative_path}: mask file not found: {mask_file.name}']

    try:
        mask_obj = nib.load(str(mask_file))
        mask = mask_obj.get_fdata()
        affine_transform = mask_obj.affine
    except Exception as exc:
        return None, None, [f'{scan.relative_path}: failed to load mask {mask_file.name}: {exc}']

    indexes = np.array(np.where(mask == 1))
    if indexes.size == 0:
        return None, None, [f'{scan.relative_path}: no voxels found in {mask_file.name}']

    index_min = indexes.min(axis=1)
    index_max = indexes.max(axis=1)
    world_min = nib.affines.apply_affine(affine_transform, index_min)
    world_max = nib.affines.apply_affine(affine_transform, index_max)

    z_direction = affine_transform[:3, 2][2]
    if z_direction == 0:
        return None, None, [f'{scan.relative_path}: affine z-direction is zero']

    z_sign = math.copysign(1, z_direction)
    z_delta = 0.5 * abs(world_max[2] - world_min[2])
    z_vertebra = float(world_max[2] - z_sign * z_delta)

    positions = sorted(z_positions.keys())
    if len(positions) == 1:
        closest_z = positions[0]
        return z_positions[closest_z], z_vertebra, []

    for z1, z2 in zip(positions[:-1], positions[1:]):
        if min(z1, z2) <= z_vertebra <= max(z1, z2):
            closest_z = min(positions, key=lambda z: abs(z - z_vertebra))
            return z_positions[closest_z], z_vertebra, []

    closest_z = min(positions, key=lambda z: abs(z - z_vertebra))
    return z_positions[closest_z], z_vertebra, [
        f'{scan.relative_path}: vertebra z-position {z_vertebra:.2f} mm outside DICOM range; selected nearest slice'
    ]


def dicom_to_png_bytes(dicom_file: Path) -> bytes:
    p = load_dicom(dicom_file)
    if p is None:
        raise ValueError(f'Could not read DICOM file: {dicom_file}')

    pixels = p.pixel_array.astype(np.float32)
    slope = float(getattr(p, 'RescaleSlope', 1))
    intercept = float(getattr(p, 'RescaleIntercept', 0))
    pixels = pixels * slope + intercept

    if hasattr(p, 'WindowCenter') and hasattr(p, 'WindowWidth'):
        wc = p.WindowCenter[0] if isinstance(p.WindowCenter, pydicom.multival.MultiValue) else p.WindowCenter
        ww = p.WindowWidth[0] if isinstance(p.WindowWidth, pydicom.multival.MultiValue) else p.WindowWidth
        wc = float(wc)
        ww = float(ww)
        pixels = np.clip(pixels, wc - ww / 2, wc + ww / 2)
    else:
        pixels = np.clip(pixels, np.percentile(pixels, 1), np.percentile(pixels, 99))

    pixels = pixels - pixels.min()
    max_value = pixels.max()
    if max_value > 0:
        pixels = pixels / max_value
    pixels = (pixels * 255).astype(np.uint8)

    if getattr(p, 'PhotometricInterpretation', '') == 'MONOCHROME1':
        pixels = 255 - pixels

    buffer = BytesIO()
    Image.fromarray(pixels).save(buffer, format='PNG')
    return buffer.getvalue()


def sagittal_review_png_bytes(scan_dir: Path, mask_file: Path, z_vertebra: float) -> bytes:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import SimpleITK as sitk

    reader = sitk.ImageSeriesReader()
    series_ids = reader.GetGDCMSeriesIDs(str(scan_dir))
    if not series_ids:
        raise ValueError(f'No DICOM series found in {scan_dir}')

    file_names = reader.GetGDCMSeriesFileNames(str(scan_dir), series_ids[0])
    reader.SetFileNames(file_names)
    ct = reader.Execute()

    vert_mask = sitk.ReadImage(str(mask_file))
    vert_mask_ref = sitk.Resample(
        vert_mask,
        ct,
        sitk.Transform(),
        sitk.sitkNearestNeighbor,
        0,
        vert_mask.GetPixelID(),
    )

    mask_arr = sitk.GetArrayFromImage(vert_mask_ref).astype(np.uint8)
    mask_indexes = np.argwhere(mask_arr > 0)
    x_index = int(round(mask_indexes[:, 2].mean())) if mask_indexes.size else ct.GetSize()[0] // 2

    size = ct.GetSize()
    y_index = size[1] // 2
    try:
        base_point = ct.TransformIndexToPhysicalPoint((x_index, y_index, size[2] // 2))
        _, _, z_index = ct.TransformPhysicalPointToIndex((base_point[0], base_point[1], z_vertebra))
    except RuntimeError:
        z_centers = np.array([
            ct.TransformIndexToPhysicalPoint((x_index, y_index, k))[2]
            for k in range(size[2])
        ])
        z_index = int(np.argmin(np.abs(z_centers - z_vertebra)))

    z_index = int(np.clip(z_index, 0, size[2] - 1))
    ct_arr = sitk.GetArrayFromImage(ct).astype(np.float32)
    sag_ct = ct_arr[:, :, x_index]
    sag_mask = mask_arr[:, :, x_index]
    vmin, vmax = np.percentile(sag_ct, (1, 99))

    spacing = ct.GetSpacing()
    aspect = spacing[2] / spacing[1]

    fig = plt.figure(figsize=(7, 9))
    plt.imshow(sag_ct, cmap='gray', vmin=vmin, vmax=vmax, origin='lower', aspect=aspect)
    plt.imshow(sag_mask, alpha=0.35, origin='lower', aspect=aspect)
    plt.axhline(z_index, linewidth=2)
    plt.title('Sagittal view with vertebral mask overlay and selected axial slice')
    plt.axis('off')

    buffer = BytesIO()
    fig.savefig(buffer, bbox_inches='tight', dpi=200, format='png')
    plt.close(fig)
    return buffer.getvalue()


def relative_output_prefix(vertebral_level: str, patient_id: str, series_uid: str) -> str:
    safe_patient = clean_filename_part(patient_id, 'unknown_patient')
    safe_series = clean_filename_part(series_uid[-12:], 'series')
    return f'{vertebral_level}_{safe_patient}_{safe_series}'


def process_scan(scan: CandidateScan, params: SliceSelectTaskParameters, temp_root: Path) -> tuple[list[OutputDatasetFile], dict[str, Any]]:
    mask_dir = temp_root / clean_filename_part(scan.series_instance_uid, 'series')
    if mask_dir.exists():
        shutil.rmtree(mask_dir)
    mask_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        'series_instance_uid': scan.series_instance_uid,
        'relative_path': scan.relative_path,
        'description': scan.description,
        'rows': scan.rows,
        'columns': scan.columns,
        'status': 'failed',
        'errors': [],
        'warnings': [],
    }

    run_totalsegmentator(scan.path, mask_dir, fast=fast_mode)
    selected_slice, z_vertebra, messages = find_selected_slice(scan, params.vertebral_level, mask_dir)
    warnings = [message for message in messages if 'outside DICOM range' in message]
    errors = [message for message in messages if message not in warnings]
    result['warnings'].extend(warnings)

    if errors or selected_slice is None or z_vertebra is None:
        result['errors'].extend(errors or ['No slice selected'])
        return [], result

    patient_id = patient_id_from_relative_path(
        scan.relative_files[0] if scan.relative_files else scan.relative_path,
        patient_id_path_part_index,
        scan.series_instance_uid[-12:],
    )
    prefix = relative_output_prefix(params.vertebral_level, patient_id, scan.series_instance_uid)
    extension = selected_slice.suffix if selected_slice.suffix else '.dcm'

    output_files = [
        OutputDatasetFile(
            relative_path=f'selected_slices/{prefix}{extension}',
            content=selected_slice.read_bytes(),
        )
    ]

    if create_review_pngs:
        output_files.append(
            OutputDatasetFile(
                relative_path=f'review/{prefix}_axial.png',
                content=dicom_to_png_bytes(selected_slice),
            )
        )
        mask_file = mask_dir / f'vertebrae_{params.vertebral_level}.nii.gz'
        output_files.append(
            OutputDatasetFile(
                relative_path=f'review/{prefix}_sagittal.png',
                content=sagittal_review_png_bytes(scan.path, mask_file, z_vertebra),
            )
        )

    result.update(
        status='completed',
        patient_id=patient_id,
        selected_slice=str(selected_slice.name),
        selected_slice_relative_output=f'selected_slices/{prefix}{extension}',
        selected_z_position_mm=z_vertebra,
    )
    return output_files, result


def run_slice_select_task(parameters: dict, user_id: str, celery_task=None) -> dict:
    runtime = TaskRuntime(
        task_key='sliceselect',
        parameters=parameters,
        parameter_model=SliceSelectTaskParameters,
        user_id=user_id,
        celery_task=celery_task,
    )
    params = runtime.params
    runtime.mark_running()

    try:
        dataset = runtime.get_input_dataset(params.dataset_id)
        scans = find_candidate_scans(dataset, user_id)
        total = len(scans)
        runtime.update_progress(current=0, total=total, message=f'Found {total} candidate DICOM series')

        output_files: list[OutputDatasetFile] = []
        summary: list[dict[str, Any]] = []

        with tempfile.TemporaryDirectory(prefix='mosamatic3_sliceselect_') as temp_dir:
            temp_root = Path(temp_dir)
            for index, scan in enumerate(scans.values()):
                current = index + 1
                runtime.check_cancelled(
                    current=index,
                    total=total,
                    message=f'Slice selection cancelled after {index} of {total} scans',
                )
                runtime.update_progress(
                    current=index,
                    total=total,
                    message=f'Processing scan {current} of {total}: {scan.relative_path}',
                )

                try:
                    files, scan_result = process_scan(scan, params, temp_root)
                    output_files.extend(files)
                    summary.append(scan_result)
                except Exception as exc:
                    summary.append({
                        'series_instance_uid': scan.series_instance_uid,
                        'relative_path': scan.relative_path,
                        'description': scan.description,
                        'status': 'failed',
                        'errors': [str(exc)],
                    })

                time.sleep(0.05)
                runtime.update_progress(
                    current=current,
                    total=total,
                    message=f'Processed scan {current} of {total}',
                )

        completed = [item for item in summary if item.get('status') == 'completed']
        failed = [item for item in summary if item.get('status') == 'failed']

        output_files.append(OutputDatasetFile(
            relative_path='summary.json',
            content=json.dumps({
                'task': 'sliceselect',
                'input_dataset_id': str(params.dataset_id),
                'vertebral_level': params.vertebral_level,
                'fast_mode': fast_mode,
                'candidate_scans': total,
                'completed_count': len(completed),
                'failed_count': len(failed),
                'results': summary,
            }, indent=2).encode('utf-8'),
        ))

        output_dataset = runtime.create_output_dataset(name='Slice Select output', files=output_files)
        message = f'Slice selection completed: {len(completed)} succeeded, {len(failed)} failed'
        runtime.update_progress(current=total, total=total, message=message)
        runtime.mark_finished()

        return {
            'current': total,
            'total': total,
            'message': message,
            'parameters': params.model_dump(mode='json'),
            'output_datasets': [DatasetSerializer(output_dataset).data],
        }
    except Ignore:
        raise
    except Exception:
        runtime.mark_failed()
        raise
