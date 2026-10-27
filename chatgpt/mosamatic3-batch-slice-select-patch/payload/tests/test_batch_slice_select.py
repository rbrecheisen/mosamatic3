import json
import tempfile
import unittest
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian

from django.core.management.base import CommandError
from core.management.commands.batch_slice_select import Command, discover
from core.processing.sliceselect import engine


def image_bytes():
    out = BytesIO()
    Image.new('L', (2, 2)).save(out, 'PNG')
    return out.getvalue()


def dicom(path, uid, sop, z):
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = sop
    d = FileDataset(str(path), {}, file_meta=meta, preamble=b'\0'*128)
    d.SOPClassUID, d.SOPInstanceUID, d.SeriesInstanceUID = CTImageStorage, sop, uid
    d.Modality, d.ImagePositionPatient = 'CT', [0, 0, z]
    d.Rows = d.Columns = 2
    d.save_as(path, enforce_file_format=True)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scan = self.root / 'patient' / 'scan'
        self.scan.mkdir(parents=True)
        for i in range(3):
            dicom(self.scan / f'{i}.dcm', '1.2.3', f'1.2.3.{i+1}', i)
        self.folder_list = self.root / 'folders.txt'
        self.folder_list.write_text(f'# comment\n"{self.scan}"\n{self.scan}\n', encoding='utf-8')
        self.output = self.root / 'output'
        self.cmd = Command(stdout=StringIO(), stderr=StringIO(), no_color=True)
        self.opts = dict(folder_list=str(self.folder_list), output_dir=str(self.output),
                         temp_dir=None, dry_run=False, overwrite=False)

    def process(self, scan, options, temp):
        self.assertEqual(len(scan.files), 3)
        return ([engine.SliceSelectArtifact('one.dcm', scan.files[1].read_bytes()),
                 engine.SliceSelectArtifact('a.png', image_bytes()),
                 engine.SliceSelectArtifact('s.png', image_bytes())],
                {'status':'completed', 'selected_slice': scan.files[1].name,
                 'selected_z_position_mm': 1., 'warnings': []})

    def test_resume_missing_png_and_changed_source(self):
        with patch.object(engine, 'process_scan', side_effect=self.process) as process:
            self.cmd.handle(**self.opts)
            self.assertEqual(process.call_count, 1)
            record_file = next((self.output / 'records').glob('*.json'))
            record = json.loads(record_file.read_text())
            self.assertEqual(record['status'], 'completed')
            self.assertEqual((self.output / record['outputs']['dicom']).read_bytes(), (self.scan / '1.dcm').read_bytes())
            self.cmd.handle(**self.opts)
            self.assertEqual(process.call_count, 1)
            (self.output / record['outputs']['sagittal']).unlink()
            self.cmd.handle(**self.opts)
            self.assertEqual(process.call_count, 2)
            (self.scan / '1.dcm').touch()
            self.cmd.handle(**self.opts)
            self.assertEqual(process.call_count, 3)

    def test_multiple_series_is_failure_without_inference(self):
        dicom(self.scan / 'other', '1.2.4', '1.2.4.1', 3)
        with patch.object(engine, 'process_scan') as process:
            with self.assertRaises(CommandError):
                self.cmd.handle(**self.opts)
        process.assert_not_called()
        record = json.loads(next((self.output / 'records').glob('*.json')).read_text())
        self.assertIn('Ambiguous folder', record['error'])

    def test_error_then_resume(self):
        with patch.object(engine, 'process_scan', side_effect=RuntimeError('model error')):
            with self.assertRaises(CommandError): self.cmd.handle(**self.opts)
        record_file = next((self.output / 'records').glob('*.json'))
        self.assertEqual(json.loads(record_file.read_text())['status'], 'failed')
        with patch.object(engine, 'process_scan', side_effect=self.process):
            self.cmd.handle(**self.opts)
        self.assertEqual(json.loads(record_file.read_text())['status'], 'completed')

    def test_dry_run_and_duplicate_uid(self):
        with patch.object(engine, 'process_scan') as process:
            self.cmd.handle(**{**self.opts, 'dry_run':True})
        process.assert_not_called()
        self.assertFalse(self.output.exists())
        dicom(self.scan / 'duplicate', '1.2.3', '1.2.3.1', 12)
        with self.assertRaisesRegex(ValueError, 'Duplicate SOP'):
            discover(self.scan)

    def test_collision_resistance_for_equal_folder_names(self):
        second = self.root / 'patient2' / 'scan'
        second.mkdir(parents=True)
        for i in range(3): dicom(second / f'{i}.dcm', '1.3.2', f'1.3.2.{i+1}', i)
        self.folder_list.write_text(f'{self.scan}\n{second}\n')
        with patch.object(engine, 'process_scan', side_effect=self.process):
            self.cmd.handle(**self.opts)
        self.assertEqual(len(list((self.output / 'selected').glob('*.dcm'))), 2)


if __name__ == '__main__':
    unittest.main()
