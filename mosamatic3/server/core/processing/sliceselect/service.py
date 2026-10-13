import json
import hashlib
import tempfile
import time
from pathlib import Path
from typing import Any
from celery.exceptions import Ignore

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

from . import engine
from .engine import CandidateScan, read_dicom_header


def process_scan(scan: CandidateScan, params: SliceSelectTaskParameters, temp_root: Path):
    """Adapt web parameters and neutral artifacts to the shared engine."""
    artifacts, result = engine.process_scan(
        scan,
        engine.SliceSelectOptions(
            vertebral_level=params.vertebral_level,
            patient_id_path_part_index=params.patient_id_path_part_index,
            fast=fast_mode,
            create_review_pngs=create_review_pngs,
        ),
        temp_root,
    )
    return [OutputDatasetFile(a.relative_path, a.content) for a in artifacts], result


def sagittal_thumbnail_overview_png_bytes(
    output_dataset: Dataset, manifest: dict[str, Any], thumbnail_width: int,
) -> bytes | None:
    root = dataset_upload_root(output_dataset.owner_id, output_dataset.id)
    relative_paths = sorted(
        relative_path
        for scan_info in manifest.get('scans', {}).values()
        if scan_info.get('status') == 'completed'
        for relative_path in scan_info.get('output_files') or []
        if relative_path.endswith('_sagittal.png')
    )
    return engine.sagittal_thumbnail_overview_png_bytes(
        [root / safe_relative_path(path) for path in relative_paths],
        thumbnail_width, columns=thumbnail_columns,
    )

MANIFEST_RELATIVE_PATH = 'slice_select_manifest.json'


fast_mode = True
create_review_pngs = True
thumbnail_columns = 5
thumbnail_overview_relative_path = 'sagittal_thumbnails.png'


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