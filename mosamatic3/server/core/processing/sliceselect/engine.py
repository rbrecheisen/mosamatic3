"""Filesystem slice-selection engine. No Django, Celery or dataset dependencies.

Call process_scan with an explicit CandidateScan and SliceSelectOptions.
Returned artifacts are in memory; persistence and resume belong to the caller.
"""
import math
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pydicom
from PIL import Image


@dataclass(frozen=True)
class SliceSelectOptions:
    vertebral_level: str = 'L3'
    patient_id_path_part_index: int = 1
    fast: bool = True
    create_review_pngs: bool = True
    patient_id: str | None = None


@dataclass(frozen=True)
class SliceSelectArtifact:
    relative_path: str
    content: bytes


def load_dicom(file_path: Path):
    # Preserve the existing common.dicom loader's fallback for missing metadata.
    try:
        return pydicom.dcmread(file_path)
    except pydicom.errors.InvalidDicomError:
        try:
            dataset = pydicom.dcmread(file_path, force=True)
            if hasattr(dataset, 'SOPClassUID'):
                if not hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                    dataset.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
                return dataset
        except pydicom.errors.InvalidDicomError:
            pass
    return None


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


def process_scan(scan: CandidateScan, params: SliceSelectOptions, temp_root: Path) -> tuple[list[SliceSelectArtifact], dict[str, Any]]:
    if not scan.files:
        raise ValueError('Cannot process a scan without DICOM files')
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='series_', dir=temp_root) as work_dir:
        work_root = Path(work_dir)
        scan_dir = work_root / 'dicom'
        mask_dir = work_root / 'masks'
        scan_dir.mkdir()
        mask_dir.mkdir()
        # Numbered names avoid collisions when source files share a basename.
        for index, source in enumerate(scan.files):
            target = scan_dir / f'{index:08d}.dcm'
            try:
                os.link(source, target)
            except OSError:
                shutil.copy2(source, target)

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

        run_totalsegmentator(scan_dir, mask_dir, fast=params.fast)
        selected_slice, z_vertebra, messages = find_selected_slice(scan, params.vertebral_level, mask_dir)
        warnings = [message for message in messages if 'outside DICOM range' in message]
        errors = [message for message in messages if message not in warnings]
        result['warnings'].extend(warnings)

        if errors or selected_slice is None or z_vertebra is None:
            result['errors'].extend(errors or ['No slice selected'])
            return [], result
        
        patient_id_path_part_index = int(params.patient_id_path_part_index)

        patient_id = params.patient_id or patient_id_from_relative_path(
            scan.relative_files[0] if scan.relative_files else scan.relative_path,
            patient_id_path_part_index,
            scan.series_instance_uid[-12:],
        )
        prefix = relative_output_prefix(params.vertebral_level, patient_id, scan.series_instance_uid)
        extension = selected_slice.suffix if selected_slice.suffix else '.dcm'

        output_files = [
            SliceSelectArtifact(
                relative_path=f'{prefix}{extension}',
                content=selected_slice.read_bytes(),
            )
        ]

        if params.create_review_pngs:
            output_files.append(
                SliceSelectArtifact(
                    relative_path=f'{prefix}_axial.png',
                    content=dicom_to_png_bytes(selected_slice),
                )
            )
            mask_file = mask_dir / f'vertebrae_{params.vertebral_level}.nii.gz'
            output_files.append(
                SliceSelectArtifact(
                    relative_path=f'{prefix}_sagittal.png',
                    content=sagittal_review_png_bytes(
                        scan_dir, mask_file,
                        float(read_dicom_header(selected_slice).ImagePositionPatient[2]),
                    ),
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


def sagittal_thumbnail_overview_png_bytes(
    image_paths: list[Path], thumbnail_width: int, *, columns: int = 5,
) -> bytes | None:
    if thumbnail_width <= 0 or columns <= 0:
        raise ValueError('Thumbnail width and columns must be positive')
    thumbnails: list[Image.Image] = []

    for image_path in image_paths:

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

    columns = min(columns, len(thumbnails))
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
