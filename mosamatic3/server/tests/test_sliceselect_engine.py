"""Run with: python -m unittest discover -s tests -p test_sliceselect_engine.py"""
import ast
import tempfile
import unittest
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import nibabel as nib
import numpy as np
import pydicom
from PIL import Image
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, CTImageStorage

from core.processing.sliceselect import engine


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.files = []
        for i, z in enumerate((0., 2., 4.)):
            path = self.source / f'{i}.dcm'
            meta = FileMetaDataset()
            meta.TransferSyntaxUID = ExplicitVRLittleEndian
            meta.MediaStorageSOPClassUID = CTImageStorage
            meta.MediaStorageSOPInstanceUID = f'1.2.3.{i+1}'
            ds = FileDataset(str(path), {}, file_meta=meta, preamble=b'\0' * 128)
            ds.SOPClassUID = CTImageStorage
            ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
            ds.SeriesInstanceUID = '1.2.3.4.5'
            ds.Modality = 'CT'
            ds.ImagePositionPatient = [0., 0., z]
            ds.Rows = ds.Columns = 2
            ds.SamplesPerPixel = 1
            ds.PhotometricInterpretation = 'MONOCHROME2'
            ds.BitsAllocated = ds.BitsStored = 16
            ds.HighBit = 15
            ds.PixelRepresentation = 1
            ds.PixelData = np.array([0, 100, 200, 300], dtype=np.int16).tobytes()
            ds.save_as(path, enforce_file_format=True)
            self.files.append(path)
        (self.source / 'unrelated.dcm').write_bytes(b'not part of this series')
        self.scan = engine.CandidateScan('1.2.3.4.5', self.source, 'root/P001/ct',
            files=self.files, relative_files=[f'root/P001/ct/{p.name}' for p in self.files])
        self.work = self.root / 'work'

    def segmentation(self, scan_dir, mask_dir, *, fast):
        self.assertTrue(fast)
        self.assertEqual(len(list(scan_dir.iterdir())), 3)
        self.assertEqual({p.read_bytes() for p in scan_dir.iterdir()}, {p.read_bytes() for p in self.files})
        mask = np.zeros((2, 2, 5), dtype=np.uint8)
        mask[:, :, 1:4] = 1
        nib.save(nib.Nifti1Image(mask, np.eye(4)), mask_dir / 'vertebrae_L3.nii.gz')

    def test_process_isolated_series_with_original_dicom_and_reviews(self):
        def review(scan_dir, mask_file, selected_z):
            self.assertEqual(len(list(scan_dir.iterdir())), 3)
            self.assertEqual(selected_z, 2.)
            return b'sagittal'
        with patch.object(engine, 'run_totalsegmentator', self.segmentation), patch.object(engine, 'sagittal_review_png_bytes', review):
            artifacts, result = engine.process_scan(self.scan, engine.SliceSelectOptions(), self.work)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['patient_id'], 'P001')
        self.assertEqual(len(artifacts), 3)
        self.assertEqual(artifacts[0].content, self.files[1].read_bytes())
        Image.open(BytesIO(artifacts[1].content)).verify()
        self.assertEqual(list(self.work.iterdir()), [])

    def test_copy_fallback_and_explicit_patient(self):
        with patch.object(engine.os, 'link', side_effect=OSError('different filesystem')), patch.object(engine, 'run_totalsegmentator', self.segmentation):
            artifacts, result = engine.process_scan(self.scan, engine.SliceSelectOptions(create_review_pngs=False, patient_id='CLI_patient'), self.work)
        self.assertEqual(result['patient_id'], 'CLI_patient')
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_cleanup_on_segmentation_failure(self):
        with patch.object(engine, 'run_totalsegmentator', side_effect=RuntimeError('segmentation failed')):
            with self.assertRaises(RuntimeError):
                engine.process_scan(self.scan, engine.SliceSelectOptions(), self.work)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_missing_mask_returns_failed_without_artifacts(self):
        with patch.object(engine, 'run_totalsegmentator', return_value=None):
            artifacts, result = engine.process_scan(self.scan, engine.SliceSelectOptions(), self.work)
        self.assertEqual(artifacts, [])
        self.assertEqual(result['status'], 'failed')
        self.assertIn('mask file not found', result['errors'][0])
        self.assertEqual(list(self.work.iterdir()), [])

    def test_zero_patient_index_is_respected(self):
        with patch.object(engine, 'run_totalsegmentator', self.segmentation):
            _, result = engine.process_scan(self.scan, engine.SliceSelectOptions(patient_id_path_part_index=0, create_review_pngs=False), self.work)
        self.assertEqual(result['patient_id'], 'root')

    def test_overview(self):
        paths = []
        for i in range(6):
            path = self.root / f'{i}.png'
            Image.new('RGB', (100, 200)).save(path)
            paths.append(path)
        data = engine.sagittal_thumbnail_overview_png_bytes(paths, 80)
        self.assertEqual(Image.open(BytesIO(data)).size, (400, 320))
        self.assertIsNone(engine.sagittal_thumbnail_overview_png_bytes([], 80))

    def test_web_adapter_and_resume(self):
        # Load the thin adapter/resume functions without initializing Django.
        tree = ast.parse(Path(engine.__file__).with_name('service.py').read_text())
        names = {'process_scan', 'scan_already_completed', 'output_files_exist'}
        functions = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
        @dataclass
        class WebArtifact:
            relative_path: str
            content: bytes
        context = dict(engine=engine, CandidateScan=engine.CandidateScan, SliceSelectTaskParameters=object,
            Path=Path, Any=object, Dataset=object, OutputDatasetFile=WebArtifact,
            fast_mode=True, create_review_pngs=True, dataset_upload_root=lambda *args: self.root,
            safe_relative_path=Path)
        exec(compile(functions, 'web-adapter', 'exec'), context)
        params = SimpleNamespace(vertebral_level='L3', patient_id_path_part_index=1)
        with patch.object(engine, 'process_scan', return_value=([engine.SliceSelectArtifact('test.dcm', b'ct')], {'status':'completed'})) as mock:
            files, _ = context['process_scan'](self.scan, params, self.work)
        self.assertIsInstance(files[0], WebArtifact)
        self.assertEqual(mock.call_args.args[1], engine.SliceSelectOptions())
        dataset = SimpleNamespace(owner_id=1, id=2)
        manifest = {'scans': {self.scan.series_instance_uid: {'status':'completed', 'output_files':['test.dcm','qa.png']}}}
        (self.root / 'test.dcm').write_bytes(b'ct')
        self.assertFalse(context['scan_already_completed'](dataset, manifest, self.scan))
        (self.root / 'qa.png').write_bytes(b'qa')
        self.assertTrue(context['scan_already_completed'](dataset, manifest, self.scan))


if __name__ == '__main__':
    unittest.main()
