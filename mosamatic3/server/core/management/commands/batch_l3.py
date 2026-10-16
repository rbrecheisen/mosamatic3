"""Submit mounted L3 DICOM images to Mosamatic3's built-in L3 pipeline in batches.

Run from the Django app/container using manage.py. Input must be mounted into the
container (read-only recommended); output state stays in the normal Django database.
"""
import csv
import hashlib
import json
import shutil
import time
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.datasets.services import dataset_upload_root
from core.models import Dataset, DatasetFile, PipelineRun
from core.pipelines.service import create_pipeline_run

PIPELINE_KEY = 'default_body_composition'


class Command(BaseCommand):
    help = 'Run the default L3 pipeline on mounted DICOMs, in resumable batches.'

    def add_arguments(self, parser):
        parser.add_argument('source', help='Container-visible directory of L3 .dcm files')
        parser.add_argument('--username', required=True, help='Existing Mosamatic3 username')
        parser.add_argument('--batch-size', type=int, default=100)
        parser.add_argument('--export-dir', default='/data/batch_l3_results')
        parser.add_argument('--poll-seconds', type=int, default=10)
        parser.add_argument('--retry-failed', action='store_true')

    def handle(self, *args, **opt):
        source = Path(opt['source']).resolve()
        export_root = Path(opt['export_dir']).resolve()
        batch_size = opt['batch_size']
        if batch_size < 1 or opt['poll_seconds'] < 1:
            raise CommandError('batch-size and poll-seconds must be positive')
        if not source.is_dir():
            raise CommandError(f'Source directory missing inside container: {source}')
        user = get_user_model().objects.filter(username=opt['username']).first()
        if user is None:
            raise CommandError(f'Unknown user: {opt["username"]}')
        files = sorted(p for p in source.rglob('*.dcm') if p.is_file())
        if not files:
            raise CommandError(f'No .dcm files found in {source}')
        # The identifier prevents accidental reuse of old datasets if a different
        # input directory is submitted. A manifest freezes batch membership.
        identity = hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:12]
        export_root.mkdir(parents=True, exist_ok=True)
        manifest = export_root / f'manifest_{identity}.json'
        relative_files = [str(p.relative_to(source).as_posix()) for p in files]
        if manifest.exists():
            old = json.loads(manifest.read_text(encoding='utf-8'))
            if old['source'] != str(source) or old['files'] != relative_files or old['batch_size'] != batch_size:
                raise CommandError('Input inventory or batch-size changed since prior run. '
                                   'Use a new export directory; do not silently reassign image batches.')
        else:
            data = {'source': str(source), 'files': relative_files, 'batch_size': batch_size}
            tmp = manifest.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
            tmp.replace(manifest)
        total = (len(files) + batch_size - 1) // batch_size
        self.stdout.write(f'{len(files)} images, {total} batches; pipeline={PIPELINE_KEY}')
        for idx in range(total):
            batch = files[idx * batch_size:(idx + 1) * batch_size]
            dataset_name = f'BATCH_L3_{identity}_{idx + 1:05d}'
            export_file = export_root / f'{dataset_name}_scores.csv'
            dataset = Dataset.objects.filter(owner=user, name=dataset_name, kind=Dataset.KIND_INPUT).first()
            if dataset is None:
                dataset = self.create_dataset(user, dataset_name, source, batch)
            elif dataset.files.count() != len(batch):
                raise CommandError(f'{dataset_name} has incomplete input data: manual inspection required')
            runs = PipelineRun.objects.filter(owner=user, initial_dataset=dataset).order_by('-created_at')
            run = runs.first()
            if run is not None and run.status in (PipelineRun.STATUS_FAILURE, PipelineRun.STATUS_CANCELED):
                if not opt['retry_failed']:
                    raise CommandError(f'{dataset_name}: run {run.id} is {run.status}. '
                                       'Investigate error, then pass --retry-failed to retry.')
                run = None
            if run is None:
                run = create_pipeline_run(user=user, config_key=PIPELINE_KEY,
                                          initial_dataset_id=dataset.id)
                self.stdout.write(f'{dataset_name}: queued run {run.id}')
            else:
                self.stdout.write(f'{dataset_name}: existing run {run.id} ({run.status})')
            while True:
                run.refresh_from_db()
                if run.status == PipelineRun.STATUS_SUCCESS:
                    break
                if run.status in (PipelineRun.STATUS_FAILURE, PipelineRun.STATUS_CANCELED):
                    raise CommandError(f'{dataset_name}: {run.status}: {run.error_message}')
                time.sleep(opt['poll_seconds'])
            step = run.step_runs.filter(step_id='calculatescores').first()
            if step is None or step.output_dataset_id is None:
                raise CommandError(f'{dataset_name}: pipeline SUCCESS but score output missing')
            src = dataset_upload_root(user.id, step.output_dataset_id) / 'bc_scores.csv'
            if not src.is_file():
                raise CommandError(f'{dataset_name}: expected output missing: {src}')
            # Overwrite the export atomically; this also repairs interrupted exports.
            temp = export_file.with_suffix('.csv.partial')
            shutil.copyfile(src, temp)
            temp.replace(export_file)
            self.stdout.write(f'{idx+1}/{total}: {export_file.name}')
        self.stdout.write(self.style.SUCCESS('All batches complete. Batch score CSVs exported.'))

    def create_dataset(self, user, name, source, files):
        root = None
        try:
            with transaction.atomic():
                dataset = Dataset.objects.create(owner=user, name=name, kind=Dataset.KIND_INPUT)
                root = dataset_upload_root(user.id, dataset.id)
                root.mkdir(parents=True, exist_ok=False)
                for path in files:
                    rel = path.relative_to(source)
                    dst = root / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, dst)
                    DatasetFile.objects.create(dataset=dataset, relative_path=rel.as_posix(),
                                               size_bytes=dst.stat().st_size)
            return dataset
        except Exception:
            if root:
                shutil.rmtree(root, ignore_errors=True)
            raise
