"""Run the Mosamatic L3 slice-selection engine on a list of CT directories."""
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from PIL import Image

from core.processing.sliceselect import engine


def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_json(path, data):
    atomic_bytes(path, (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))


def read_folders(path):
    folders, seen = [], set()
    for number, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith('#'):
            continue
        if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
            text = text[1:-1]
        folder = Path(text).expanduser()
        if not folder.is_absolute():
            folder = path.parent / folder
        folder = folder.resolve()
        key = os.path.normcase(str(folder))
        if key not in seen:
            folders.append((number, folder))
            seen.add(key)
    if not folders:
        raise ValueError('The folder list is empty')
    return folders


def discover(folder):
    if not folder.is_dir():
        raise ValueError(f'Folder does not exist or is not accessible: {folder}')
    series, invalid = {}, []
    for file in sorted(folder.iterdir()):
        if not file.is_file():
            continue
        header = engine.read_dicom_header(file)
        if header is None or str(getattr(header, 'Modality', '')).upper() != 'CT':
            continue
        uid = str(getattr(header, 'SeriesInstanceUID', '') or '')
        sop = str(getattr(header, 'SOPInstanceUID', '') or '')
        if not uid or not sop:
            invalid.append(f'{file.name}: missing SeriesInstanceUID or SOPInstanceUID')
            continue
        if int(getattr(header, 'NumberOfFrames', 1) or 1) != 1:
            invalid.append(f'{file.name}: multiframe CT is not supported')
            continue
        pos = getattr(header, 'ImagePositionPatient', None)
        try:
            z = float(pos[2])
        except (TypeError, ValueError, IndexError):
            invalid.append(f'{file.name}: missing or invalid ImagePositionPatient')
            continue
        series.setdefault(uid, []).append((file, header, sop, z))
    if invalid:
        raise ValueError('; '.join(invalid[:8]) + ('; ...' if len(invalid) > 8 else ''))
    if not series:
        raise ValueError('No readable CT DICOM series in this folder')
    if len(series) != 1:
        raise ValueError(f'Ambiguous folder: found {len(series)} CT series; expected exactly one')
    uid, entries = next(iter(series.items()))
    if len(entries) < 2:
        raise ValueError('CT series contains fewer than two single-frame images')
    sops = [e[2] for e in entries]
    if len(sops) != len(set(sops)):
        raise ValueError('Duplicate SOPInstanceUIDs in CT series; resolve before processing')
    if len({e[3] for e in entries}) != len(entries):
        raise ValueError('Duplicate slice Z positions; review CT series geometry before processing')
    first = entries[0][1]
    scan = engine.CandidateScan(series_instance_uid=uid, path=folder, relative_path=str(folder),
        description=str(getattr(first, 'SeriesDescription', '') or ''),
        rows=int(getattr(first, 'Rows', -1) or -1), columns=int(getattr(first, 'Columns', -1) or -1),
        files=[e[0] for e in entries], relative_files=[e[0].name for e in entries])
    # Detect changed source inventory; this is not a content checksum.
    details = [(e[0].name, e[2], e[0].stat().st_size, e[0].stat().st_mtime_ns) for e in entries]
    fingerprint = hashlib.sha256(json.dumps(details, ensure_ascii=False).encode()).hexdigest()
    return scan, fingerprint


def outputs_valid(record, output):
    if record.get('status') != 'completed':
        return False
    try:
        paths = record['outputs']
        dicom = output / paths['dicom']
        header = engine.read_dicom_header(dicom)
        if not header or str(getattr(header, 'SOPInstanceUID', '')) != record['selected_sop_instance_uid']:
            return False
        for kind in ('axial', 'sagittal'):
            with Image.open(output / paths[kind]) as im:
                im.verify()
        return True
    except (OSError, KeyError, ValueError, TypeError):
        return False


def report(output, entries):
    fields = ['source_folder', 'status', 'series_uid', 'slice_count', 'selected_source_file',
              'selected_sop_instance_uid', 'selected_z_position_mm', 'dicom', 'axial', 'sagittal',
              'warnings', 'error']
    from io import StringIO
    stream = StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for entry in entries:
        paths = entry.get('outputs', {})
        row = {k: entry.get(k, '') for k in fields}
        row.update({k: paths.get(k, '') for k in ('dicom', 'axial', 'sagittal')})
        row['warnings'] = '; '.join(entry.get('warnings', []))
        writer.writerow(row)
    atomic_bytes(output / 'batch_slice_select_report.csv', ('\ufeff' + stream.getvalue()).encode('utf-8'))


class Command(BaseCommand):
    help = 'Run L3 selection on CT folders listed in a UTF-8 text file.'

    def add_arguments(self, parser):
        parser.add_argument('folder_list', help='UTF-8 text file containing one container-visible scan folder per line')
        parser.add_argument('--output-dir', required=True, help='Writable persistent output directory')
        parser.add_argument('--temp-dir', help='Writable directory for temporary DICOMs and segmentation masks')
        parser.add_argument('--dry-run', action='store_true', help='Inspect folders only; do not run inference or write outputs')
        parser.add_argument('--overwrite', action='store_true', help='Rerun completed scans')

    def handle(self, *args, **opts):
        list_path = Path(opts['folder_list']).expanduser().resolve()
        output = Path(opts['output_dir']).expanduser().resolve()
        try:
            folders = read_folders(list_path)
        except (OSError, ValueError) as exc:
            raise CommandError(f'Cannot read folder list: {exc}') from exc
        temp_dir = Path(opts['temp_dir']).expanduser().resolve() if opts['temp_dir'] else None
        if temp_dir and not temp_dir.is_dir():
            raise CommandError(f'Temporary directory does not exist: {temp_dir}')
        if not opts['dry_run']:
            output.mkdir(parents=True, exist_ok=True)
        records, failed, done, skipped = [], 0, 0, 0
        with tempfile.TemporaryDirectory(prefix='mosamatic_batch_slice_', dir=temp_dir) as tmp:
            for number, (line, folder) in enumerate(folders, 1):
                self.stdout.write(f'[{number}/{len(folders)}] {folder}')
                identity = hashlib.sha256(os.path.normcase(str(folder)).encode('utf-8')).hexdigest()[:16]
                base = engine.clean_filename_part(folder.name, 'scan')[:80] + '_' + identity
                rec_path = output / 'records' / f'{base}.json'
                record = {'source_folder': str(folder), 'line': line, 'status': 'failed', 'error': ''}
                try:
                    if folder == output or output in folder.parents:
                        raise ValueError('Scan folder is inside the output directory')
                    scan, fingerprint = discover(folder)
                    record.update(series_uid=scan.series_instance_uid, slice_count=len(scan.files),
                                  source_fingerprint=fingerprint)
                    if opts['dry_run']:
                        record['status'] = 'ready'
                        self.stdout.write(f'  READY: {len(scan.files)} slices; series {scan.series_instance_uid}')
                    else:
                        old = json.loads(rec_path.read_text(encoding='utf-8')) if rec_path.is_file() else {}
                        if old.get('source_fingerprint') == fingerprint and not opts['overwrite'] and outputs_valid(old, output):
                            record = old
                            skipped += 1
                            self.stdout.write('  SKIPPED: completed outputs present')
                        else:
                            artifacts, result = engine.process_scan(scan, engine.SliceSelectOptions(patient_id=folder.name), Path(tmp))
                            if result.get('status') != 'completed' or len(artifacts) != 3:
                                raise ValueError('; '.join(result.get('errors', [])) or 'Selection did not produce all three artifacts')
                            selected = folder / result['selected_slice']
                            header = engine.read_dicom_header(selected)
                            sop = str(getattr(header, 'SOPInstanceUID', '') or '')
                            if not sop:
                                raise ValueError('Selected slice has no SOPInstanceUID')
                            paths = {'dicom': f'selected/{base}.dcm', 'axial': f'axial/{base}_axial.png',
                                     'sagittal': f'sagittal/{base}_sagittal.png'}
                            # Clear the old completion record and DICOM before replacing the PNGs.
                            # The final DICOM is committed last; record is committed after validation.
                            rec_path.unlink(missing_ok=True)
                            (output / paths['dicom']).unlink(missing_ok=True)
                            atomic_bytes(output / paths['axial'], artifacts[1].content)
                            atomic_bytes(output / paths['sagittal'], artifacts[2].content)
                            atomic_bytes(output / paths['dicom'], artifacts[0].content)
                            record.update(status='completed', outputs=paths, selected_source_file=str(selected),
                                selected_sop_instance_uid=sop, selected_z_position_mm=result.get('selected_z_position_mm'),
                                warnings=result.get('warnings', []))
                            if not outputs_valid(record, output):
                                raise ValueError('Written output failed validation')
                            done += 1
                            self.stdout.write(f'  COMPLETED: {paths["dicom"]}')
                except Exception as exc:
                    record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
                    failed += 1
                    self.stderr.write(f'  FAILED: {record["error"]}')
                records.append(record)
                if not opts['dry_run']:
                    atomic_json(rec_path, record)
                    report(output, records)
        self.stdout.write(f'Finished: {done} completed, {skipped} skipped, {failed} failed' + (' (dry run)' if opts['dry_run'] else ''))
        if failed:
            raise CommandError(f'{failed} folder(s) failed. Review the output above' + ('.' if opts['dry_run'] else ' and batch_slice_select_report.csv.'))
