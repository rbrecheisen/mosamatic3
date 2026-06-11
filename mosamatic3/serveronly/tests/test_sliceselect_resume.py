import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from celery.exceptions import Ignore
from django.contrib.auth.models import User

from core.datasets.services import dataset_upload_root, safe_relative_path
from core.models import Dataset, DatasetFile, TaskRun
from core.processing.sliceselect import service as sliceselect_service


class FakeCeleryTask:
    def __init__(self, task_id: str):
        self.request = type('Request', (), {'id': task_id})()
        self.states = []

    def update_state(self, *, state, meta):
        self.states.append({'state': state, 'meta': meta})


def register_existing_dicom_folder_as_dataset(*, user, folder: Path) -> Dataset:
    """
    Register an existing DICOM folder as a Mosamatic Dataset without copying files.

    DatasetFile.relative_path values intentionally include the root folder name:

        abdomen/patient1/...
        abdomen/patient2/...

    This means patient_id_path_part_index=1 resolves to patient1 / patient2.
    """
    dataset = Dataset.objects.create(
        owner=user,
        name='abdomen-test-dataset',
        kind='input',
        status='ready',
    )

    file_count = 0

    for file_path in sorted(folder.rglob('*')):
        if not file_path.is_file():
            continue

        relative_path = Path(folder.name) / file_path.relative_to(folder)

        DatasetFile.objects.create(
            dataset=dataset,
            relative_path=relative_path.as_posix(),
            size_bytes=file_path.stat().st_size,
        )
        file_count += 1

    assert file_count > 0, f'No files found in {folder}'

    return dataset


def patch_input_file_lookup_to_real_folder(monkeypatch, *, folder: Path):
    """
    The app normally expects files below:

        UPLOAD_ROOT / user_id / dataset_id / relative_path

    For this integration test, the input files stay in:

        M:\\data\\mosamatic\\test\\CT\\abdomen

    So we patch get_dataset_file_path() inside sliceselect_service.
    """

    def get_dataset_file_path_from_real_folder(user_id, dataset_id, relative_path: str) -> Path:
        relative = Path(relative_path.replace('\\', '/'))

        # DatasetFile.relative_path starts with "abdomen/...".
        # Strip that first part because `folder` already points to ".../abdomen".
        parts = relative.parts
        if parts and parts[0] == folder.name:
            relative = Path(*parts[1:])

        return folder / relative

    monkeypatch.setattr(
        sliceselect_service,
        'get_dataset_file_path',
        get_dataset_file_path_from_real_folder,
    )


def load_manifest(dataset: Dataset) -> dict:
    manifest_path = (
        dataset_upload_root(dataset.owner_id, dataset.id)
        / safe_relative_path(sliceselect_service.MANIFEST_RELATIVE_PATH)
    )
    assert manifest_path.exists(), f'Manifest not found: {manifest_path}'
    return json.loads(manifest_path.read_text(encoding='utf-8'))


@pytest.mark.django_db
@pytest.mark.integration
def test_sliceselect_cancel_then_resume_with_real_totalsegmentator(
    tmp_path,
    settings,
    monkeypatch,
):
    abdomen_path = os.getenv('MOSAMATIC_TEST_ABDOMEN_PATH')

    if not abdomen_path:
        pytest.skip(
            'Set MOSAMATIC_TEST_ABDOMEN_PATH to run this test, for example: '
            r'M:\data\mosamatic\test\CT\abdomen'
        )

    abdomen_folder = Path(abdomen_path)

    assert abdomen_folder.exists(), f'Folder does not exist: {abdomen_folder}'
    assert (abdomen_folder / 'patient1').exists(), 'Expected patient1 folder'
    assert (abdomen_folder / 'patient2').exists(), 'Expected patient2 folder'

    settings.UPLOAD_ROOT = tmp_path / 'uploads'
    settings.UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    user = User.objects.create_user(
        username='resume-test-user',
        password='test',
    )

    input_dataset = register_existing_dicom_folder_as_dataset(
        user=user,
        folder=abdomen_folder,
    )

    patch_input_file_lookup_to_real_folder(
        monkeypatch,
        folder=abdomen_folder,
    )

    scans = sliceselect_service.find_candidate_scans(input_dataset, str(user.id))

    assert len(scans) == 2, (
        f'Expected exactly 2 DICOM series/scans, found {len(scans)}. '
        f'Series found: {list(scans.keys())}'
    )

    parameters = {
        'dataset_id': str(input_dataset.id),
        'vertebral_level': 'L3',
        'patient_id_path_part_index': 1,
    }

    real_process_scan = sliceselect_service.process_scan

    # ------------------------------------------------------------------
    # First run:
    # Actually process scan 1 with TotalSegmentator.
    # Then request cancellation so the task stops before scan 2.
    # ------------------------------------------------------------------

    first_run_task_id = str(uuid4())
    first_task = FakeCeleryTask(first_run_task_id)

    TaskRun.objects.create(
        owner=user,
        task_key='sliceselect',
        celery_task_id=first_run_task_id,
        status='queued',
        cancel_requested=False,
    )

    first_run_processed_series = []

    def process_scan_then_cancel(scan, params, temp_root):
        result = real_process_scan(scan, params, temp_root)

        first_run_processed_series.append(scan.series_instance_uid)

        TaskRun.objects.filter(celery_task_id=first_run_task_id).update(
            cancel_requested=True,
            status='cancel_requested',
        )

        return result

    monkeypatch.setattr(
        sliceselect_service,
        'process_scan',
        process_scan_then_cancel,
    )

    with pytest.raises(Ignore):
        sliceselect_service.run_slice_select_task(
            parameters,
            str(user.id),
            celery_task=first_task,
        )

    output_dataset = Dataset.objects.get(
        owner=user,
        kind='output',
        source_task_key='sliceselect',
        source_dataset=input_dataset,
    )

    assert output_dataset.status == 'cancelled'
    assert len(first_run_processed_series) == 1

    manifest_after_cancel = load_manifest(output_dataset)

    assert manifest_after_cancel['status'] == 'cancelled'
    assert manifest_after_cancel['candidate_scans'] == 2
    assert manifest_after_cancel['completed_count'] == 1
    assert len(manifest_after_cancel['scans']) == 1

    completed_scan_uid = first_run_processed_series[0]
    completed_scan_info = manifest_after_cancel['scans'][completed_scan_uid]

    assert completed_scan_info['status'] == 'completed'
    assert completed_scan_info['patient_id'] in {'patient1', 'patient2'}
    assert completed_scan_info['output_files']

    for relative_output_file in completed_scan_info['output_files']:
        output_path = (
            dataset_upload_root(output_dataset.owner_id, output_dataset.id)
            / safe_relative_path(relative_output_file)
        )
        assert output_path.exists(), f'Expected output file to exist: {output_path}'
        assert output_path.stat().st_size > 0, f'Expected non-empty output file: {output_path}'

    # ------------------------------------------------------------------
    # Second run:
    # Resume.
    # The already completed scan should be skipped.
    # TotalSegmentator should only run for the remaining scan.
    # ------------------------------------------------------------------

    second_run_task_id = str(uuid4())
    second_task = FakeCeleryTask(second_run_task_id)

    TaskRun.objects.create(
        owner=user,
        task_key='sliceselect',
        celery_task_id=second_run_task_id,
        status='queued',
        cancel_requested=False,
    )

    second_run_processed_series = []

    def process_scan_record_only(scan, params, temp_root):
        second_run_processed_series.append(scan.series_instance_uid)
        return real_process_scan(scan, params, temp_root)

    monkeypatch.setattr(
        sliceselect_service,
        'process_scan',
        process_scan_record_only,
    )

    result = sliceselect_service.run_slice_select_task(
        parameters,
        str(user.id),
        celery_task=second_task,
    )

    output_dataset.refresh_from_db()

    assert output_dataset.status == 'done'

    # Critical resume assertion:
    # The second run must not reprocess the scan that was already completed.
    assert len(second_run_processed_series) == 1
    assert second_run_processed_series[0] != completed_scan_uid

    manifest_after_resume = load_manifest(output_dataset)

    assert manifest_after_resume['status'] == 'done'
    assert manifest_after_resume['candidate_scans'] == 2
    assert manifest_after_resume['completed_count'] == 2
    assert len(manifest_after_resume['scans']) == 2

    for scan_uid, scan_info in manifest_after_resume['scans'].items():
        assert scan_info['status'] == 'completed'
        assert scan_info['patient_id'] in {'patient1', 'patient2'}
        assert scan_info['output_files']

        for relative_output_file in scan_info['output_files']:
            output_path = (
                dataset_upload_root(output_dataset.owner_id, output_dataset.id)
                / safe_relative_path(relative_output_file)
            )
            assert output_path.exists(), f'Expected output file to exist: {output_path}'
            assert output_path.stat().st_size > 0, f'Expected non-empty output file: {output_path}'

    # Critical dataset reuse assertion:
    # Resume should use the existing cancelled output dataset, not create another one.
    assert Dataset.objects.filter(
        owner=user,
        kind='output',
        source_task_key='sliceselect',
        source_dataset=input_dataset,
    ).count() == 1

    assert str(output_dataset.id) == result['output_datasets'][0]['id']

    first_task_run = TaskRun.objects.get(celery_task_id=first_run_task_id)
    second_task_run = TaskRun.objects.get(celery_task_id=second_run_task_id)

    assert first_task_run.status == 'cancelled'
    assert second_task_run.status == 'finished'