import json
import hashlib
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
from ...datasets.services import (
    OutputDatasetFile,
    append_output_files_to_dataset,
    create_empty_output_dataset_for_user_id,
    dataset_upload_root,
    get_dataset_file_path,
    safe_relative_path,
)
from ...models import Dataset
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import SliceSelectTaskParameters

MANIFEST_RELATIVE_PATH = 'slice_select_manifest.json'


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
thumbnail_columns = 5
thumbnail_overview_relative_path = 'sagittal_thumbnails.png'


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
    if part_index < 0:
        return clean_filename_part(fallback, 'single_scan')
    if directory_parts and 0 <= part_index < len(directory_parts):
        return clean_filename_part(directory_parts[part_index], fallback)
    if directory_parts:
        return clean_filename_part(directory_parts[0], fallback)
    return clean_filename_part(fallback, 'single_scan')


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


def sagittal_thumbnail_overview_png_bytes(
    output_dataset: Dataset,
    manifest: dict[str, Any],
    thumbnail_width: int,
) -> bytes | None:
    root = dataset_upload_root(output_dataset.owner_id, output_dataset.id)

    sagittal_paths: list[str] = []

    for scan_info in manifest.get('scans', {}).values():
        if scan_info.get('status') != 'completed':
            continue

        for relative_path in scan_info.get('output_files') or []:
            if relative_path.endswith('_sagittal.png'):
                sagittal_paths.append(relative_path)

    sagittal_paths = sorted(sagittal_paths)

    if not sagittal_paths:
        return None

    thumbnails: list[Image.Image] = []

    for relative_path in sagittal_paths:
        image_path = root / safe_relative_path(relative_path)

        if not image_path.exists() or not image_path.is_file():
            continue

        with Image.open(image_path) as image:
            image = image.convert('RGB')

            width, height = image.size
            if width <= 0 or height <= 0:
                continue

            thumbnail_height = max(1, int(round(height * thumbnail_width / width)))
            thumbnail = image.resize((thumbnail_width, thumbnail_height), Image.Resampling.LANCZOS)
            thumbnails.append(thumbnail)

    if not thumbnails:
        return None

    columns = min(thumbnail_columns, len(thumbnails))
    rows = math.ceil(len(thumbnails) / columns)

    cell_width = thumbnail_width
    cell_height = max(image.height for image in thumbnails)

    overview = Image.new(
        'RGB',
        (columns * cell_width, rows * cell_height),
        color='white',
    )

    for index, thumbnail in enumerate(thumbnails):
        row = index // columns
        column = index % columns

        x = column * cell_width
        # y = row * cell_height + (cell_height - thumbnail.height) // 2
        y = row * cell_height

        overview.paste(thumbnail, (x, y))

    buffer = BytesIO()
    overview.save(buffer, format='PNG')
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
    
    patient_id_path_part_index = int(params.patient_id_path_part_index or 1)

    patient_id = patient_id_from_relative_path(
        scan.relative_files[0] if scan.relative_files else scan.relative_path,
        patient_id_path_part_index,
        scan.series_instance_uid[-12:],
    )
    prefix = relative_output_prefix(params.vertebral_level, patient_id, scan.series_instance_uid)
    extension = selected_slice.suffix if selected_slice.suffix else '.dcm'

    output_files = [
        OutputDatasetFile(
            relative_path=f'{prefix}{extension}',
            content=selected_slice.read_bytes(),
        )
    ]

    if create_review_pngs:
        output_files.append(
            OutputDatasetFile(
                relative_path=f'{prefix}_axial.png',
                content=dicom_to_png_bytes(selected_slice),
            )
        )
        mask_file = mask_dir / f'vertebrae_{params.vertebral_level}.nii.gz'
        output_files.append(
            OutputDatasetFile(
                relative_path=f'{prefix}_sagittal.png',
                content=sagittal_review_png_bytes(scan.path, mask_file, z_vertebra),
            )
        )

    result.update(
        status='completed',
        patient_id=patient_id,
        selected_slice=str(selected_slice.name),
        selected_slice_relative_output=f'{prefix}{extension}',
        selected_z_position_mm=z_vertebra,
    )
    return output_files, result


def parameters_hash(params: SliceSelectTaskParameters) -> str:
    payload = params.model_dump(mode='json')
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def empty_manifest(*, params: SliceSelectTaskParameters, parameter_hash: str, input_dataset: Dataset) -> dict[str, Any]:
    return {
        'task': 'sliceselect',
        'input_dataset_id': str(input_dataset.id),
        'input_dataset_name': input_dataset.name,
        'vertebral_level': params.vertebral_level,
        'thumbnail_width': params.thumbnail_width,
        'thumbnail_overview': thumbnail_overview_relative_path,
        'fast_mode': fast_mode,
        'parameter_hash': parameter_hash,
        'status': 'in_progress',
        'candidate_scans': 0,
        'completed_count': 0,
        'failed_count': 0,
        'skipped_count': 0,
        'scans': {},
    }


def load_manifest(output_dataset: Dataset) -> dict[str, Any] | None:
    path = dataset_upload_root(output_dataset.owner_id, output_dataset.id) / safe_relative_path(MANIFEST_RELATIVE_PATH)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def save_manifest(output_dataset: Dataset, manifest: dict[str, Any]) -> None:
    append_output_files_to_dataset(
        output_dataset,
        [
            OutputDatasetFile(
                relative_path=MANIFEST_RELATIVE_PATH,
                content=json.dumps(manifest, indent=2).encode('utf-8'),
            )
        ],
    )


def manifest_counts(manifest: dict[str, Any]) -> tuple[int, int, int]:
    scans = manifest.get('scans', {})
    completed = sum(1 for item in scans.values() if item.get('status') == 'completed')
    failed = sum(1 for item in scans.values() if item.get('status') == 'failed')
    skipped = sum(1 for item in scans.values() if item.get('status') == 'skipped')
    return completed, failed, skipped


def update_manifest_counts(manifest: dict[str, Any]) -> None:
    completed, failed, skipped = manifest_counts(manifest)
    manifest['completed_count'] = completed
    manifest['failed_count'] = failed
    manifest['skipped_count'] = skipped


def output_files_exist(output_dataset: Dataset, relative_paths: list[str]) -> bool:
    root = dataset_upload_root(output_dataset.owner_id, output_dataset.id)

    for relative_path in relative_paths:
        path = root / safe_relative_path(relative_path)
        if not path.exists() or not path.is_file():
            return False

    return True


def scan_already_completed(output_dataset: Dataset, manifest: dict[str, Any], scan: CandidateScan) -> bool:
    scan_info = manifest.get('scans', {}).get(scan.series_instance_uid)

    if not scan_info:
        return False

    if scan_info.get('status') != 'completed':
        return False

    output_files = scan_info.get('output_files') or []

    if not output_files:
        return False

    return output_files_exist(output_dataset, output_files)


def get_or_create_slice_select_output_dataset(
    *,
    runtime: TaskRuntime,
    input_dataset: Dataset,
    params: SliceSelectTaskParameters,
    parameter_hash: str,
) -> tuple[Dataset, dict[str, Any]]:
    output_dataset = Dataset.objects.filter(
        owner_id=runtime.user_id,
        kind='output',
        source_task_key='sliceselect',
        source_dataset=input_dataset,
        parameter_hash=parameter_hash,
        status__in=['in_progress', 'cancelled', 'failed'],
    ).order_by('-created_at').first()

    if output_dataset is None:
        output_dataset = create_empty_output_dataset_for_user_id(
            name=f'Slice Select output - {input_dataset.name}',
            user_id=runtime.user_id,
            source_task_key='sliceselect',
            source_task_id=runtime.task_id,
            source_dataset=input_dataset,
            parameter_hash=parameter_hash,
            status='in_progress',
        )

        manifest = empty_manifest(
            params=params,
            parameter_hash=parameter_hash,
            input_dataset=input_dataset,
        )
        save_manifest(output_dataset, manifest)
        return output_dataset, manifest

    output_dataset.status = 'in_progress'
    output_dataset.source_task_id = runtime.task_id
    output_dataset.save(update_fields=['status', 'source_task_id'])

    manifest = load_manifest(output_dataset)

    if manifest is None:
        manifest = empty_manifest(
            params=params,
            parameter_hash=parameter_hash,
            input_dataset=input_dataset,
        )
        save_manifest(output_dataset, manifest)

    return output_dataset, manifest


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

    output_dataset: Dataset | None = None

    try:
        dataset = runtime.get_input_dataset(params.dataset_id)
        parameter_hash = parameters_hash(params)

        output_dataset, manifest = get_or_create_slice_select_output_dataset(
            runtime=runtime,
            input_dataset=dataset,
            params=params,
            parameter_hash=parameter_hash,
        )

        scans = find_candidate_scans(dataset, user_id)
        total = len(scans)

        manifest['candidate_scans'] = total
        manifest['status'] = 'in_progress'
        save_manifest(output_dataset, manifest)

        runtime.update_progress(
            current=0,
            total=total,
            message=f'Found {total} candidate DICOM series',
        )

        with tempfile.TemporaryDirectory(prefix='mosamatic3_sliceselect_') as temp_dir:
            temp_root = Path(temp_dir)

            for index, scan in enumerate(scans.values()):
                current = index + 1

                runtime.check_cancelled(
                    current=index,
                    total=total,
                    message=f'Slice selection cancelled after {index} of {total} scans',
                )

                if scan_already_completed(output_dataset, manifest, scan):
                    runtime.update_progress(
                        current=current,
                        total=total,
                        message=f'Skipping scan {current} of {total}: already completed',
                    )
                    continue

                runtime.update_progress(
                    current=index,
                    total=total,
                    message=f'Processing scan {current} of {total}: {scan.relative_path}',
                )

                try:
                    files, scan_result = process_scan(scan, params, temp_root)

                    scan_result['output_files'] = [file.relative_path for file in files]

                    append_output_files_to_dataset(output_dataset, files)

                    manifest.setdefault('scans', {})[scan.series_instance_uid] = scan_result
                    update_manifest_counts(manifest)
                    save_manifest(output_dataset, manifest)

                except Exception as exc:
                    manifest.setdefault('scans', {})[scan.series_instance_uid] = {
                        'series_instance_uid': scan.series_instance_uid,
                        'relative_path': scan.relative_path,
                        'description': scan.description,
                        'status': 'failed',
                        'errors': [str(exc)],
                        'output_files': [],
                    }
                    update_manifest_counts(manifest)
                    save_manifest(output_dataset, manifest)

                time.sleep(0.05)

                runtime.update_progress(
                    current=current,
                    total=total,
                    message=f'Processed scan {current} of {total}',
                )

        update_manifest_counts(manifest)

        completed_count = manifest.get('completed_count', 0)
        failed_count = manifest.get('failed_count', 0)

        if completed_count == 0:
            manifest['status'] = 'failed'
            save_manifest(output_dataset, manifest)

            output_dataset.status = 'failed'
            output_dataset.save(update_fields=['status'])

            message = f'Slice selection failed: no {params.vertebral_level} slice was selected from {total} candidate scan(s)'

            runtime.update_progress(
                current=total,
                total=total,
                message=message,
            )

            raise RuntimeError(message)

        if create_review_pngs and completed_count > 0:
            overview_png = sagittal_thumbnail_overview_png_bytes(
                output_dataset=output_dataset,
                manifest=manifest,
                thumbnail_width=params.thumbnail_width,
            )

            if overview_png is not None:
                append_output_files_to_dataset(
                    output_dataset,
                    [
                        OutputDatasetFile(
                            relative_path=thumbnail_overview_relative_path,
                            content=overview_png,
                        )
                    ],
                )

                manifest['thumbnail_overview'] = thumbnail_overview_relative_path
                manifest['thumbnail_width'] = params.thumbnail_width

        manifest['status'] = 'done'
        save_manifest(output_dataset, manifest)

        output_dataset.status = 'done'
        output_dataset.save(update_fields=['status'])

        message = f'Slice selection completed: {completed_count} succeeded, {failed_count} failed'

        runtime.update_progress(
            current=total,
            total=total,
            message=message,
        )

        runtime.mark_finished()

        return {
            'current': total,
            'total': total,
            'message': message,
            'parameters': params.model_dump(mode='json'),
            'output_datasets': [DatasetSerializer(output_dataset).data],
        }

    except Ignore:
        if output_dataset is not None:
            manifest = load_manifest(output_dataset) or {}
            manifest['status'] = 'cancelled'
            save_manifest(output_dataset, manifest)

            output_dataset.status = 'cancelled'
            output_dataset.save(update_fields=['status'])

        raise

    except Exception:
        if output_dataset is not None:
            manifest = load_manifest(output_dataset) or {}
            manifest['status'] = 'failed'
            save_manifest(output_dataset, manifest)

            output_dataset.status = 'failed'
            output_dataset.save(update_fields=['status'])

        runtime.mark_failed()
        raise