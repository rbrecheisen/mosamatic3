"""Pure-Python regression tests for processing diagnostics.

Run with: python -m pytest tests/test_processing_errors.py -q
"""
from types import SimpleNamespace

import numpy as np
import pytest

from core.tasking.errors import (
    ProcessingInputError,
    decode_single_grayscale_image,
    describe_task_error,
    require_single_grayscale_image,
)


def dicom(pixels, **overrides):
    values = dict(Rows=512, Columns=512, SamplesPerPixel=1, pixel_array=pixels)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_standard_single_frame_grayscale_is_accepted():
    pixels = np.zeros((512, 512), dtype=np.int16)
    assert require_single_grayscale_image(dicom(pixels), pixels, 'image.dcm') is pixels


@pytest.mark.parametrize('pixels,extra', [
    (np.zeros((1, 512, 512)), {'NumberOfFrames': 1}),
    (np.zeros((3, 512, 512)), {'NumberOfFrames': 3}),
    (np.zeros((512, 512, 3)), {'SamplesPerPixel': 3}),
    (np.zeros((400, 512)), {}),
])
def test_invalid_image_dimensions_report_file_shape_and_metadata(pixels, extra):
    with pytest.raises(ProcessingInputError) as exc:
        decode_single_grayscale_image(dicom(pixels, **extra), 'patient2/img.dcm')
    message = str(exc.value)
    assert 'patient2/img.dcm' in message
    assert 'shape=' in message
    assert 'NumberOfFrames=' in message
    assert 'SamplesPerPixel=' in message
    assert 'Expected one 2D grayscale CT image' in message


def test_singular_2d_array_with_multiframe_header_is_rejected():
    pixels = np.zeros((512, 512))
    with pytest.raises(ProcessingInputError, match='NumberOfFrames=2'):
        decode_single_grayscale_image(dicom(pixels, NumberOfFrames=2), 'image.dcm')


def test_decode_failure_identifies_the_file_without_traceback():
    class Broken:
        Rows = 512
        Columns = 512
        SamplesPerPixel = 1

        @property
        def pixel_array(self):
            raise RuntimeError('codec unavailable')

    with pytest.raises(ProcessingInputError) as exc:
        decode_single_grayscale_image(Broken(), 'broken.dcm')
    assert 'broken.dcm' in str(exc.value)
    assert 'codec unavailable' in str(exc.value)
    assert 'Transfer Syntax' in str(exc.value)


def test_error_summary_is_bounded_and_preserves_actionable_detail():
    assert describe_task_error(ProcessingInputError('Unsupported DICOM dimensions')) == 'Unsupported DICOM dimensions'
    assert describe_task_error(KeyError('bad-column')).startswith('KeyError:')
    assert len(describe_task_error('x' * 5000)) == 1800
