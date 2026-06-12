import os
import numpy as np
import pydicom
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)
from .utils import apply_window_center_and_width, convert_numpy_array_to_png_image


def is_dicom(f):
    try:
        pydicom.dcmread(f, stop_before_pixels=True)
        return True
    except pydicom.errors.InvalidDicomError:
        pass
    return False
    

def load_dicom(f, stop_before_pixels=False):
    try:
        return pydicom.dcmread(f, stop_before_pixels=stop_before_pixels)
    except pydicom.errors.InvalidDicomError:
        try:
            p = pydicom.dcmread(f, stop_before_pixels=stop_before_pixels, force=True)
            if hasattr(p, 'SOPClassUID'):
                if not hasattr(p.file_meta, 'TransferSyntaxUID'):
                    print(f'DICOM file {f} does not have FileMetaData/TransferSyntaxUID, trying to fix...')
                    p.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
                return p
        except pydicom.errors.InvalidDicomError:
            pass
    return None


def is_jpeg2000_compressed(p):
    if hasattr(p.file_meta, 'TransferSyntaxUID'):
        return p.file_meta.TransferSyntaxUID not in [ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian]
    return False


def get_rescale_params(p):
    rescale_slope = getattr(p, 'RescaleSlope', None)
    rescale_intercept = getattr(p, 'RescaleIntercept', None)
    if rescale_slope is not None and rescale_intercept is not None:
        return rescale_slope, rescale_intercept
    # Try Enhanced DICOM structure
    if 'SharedFunctionalGroupsSequence' in p:
        fg = p.SharedFunctionalGroupsSequence[0]
        if 'PixelValueTransformationSequence' in fg:
            pvt = fg.PixelValueTransformationSequence[0]
            rescale_slope = pvt.get('RescaleSlope', 1)
            rescale_intercept = pvt.get('RescaleIntercept', 0)
            return rescale_slope, rescale_intercept
    return 1, 0


def get_pixels_from_dicom_object(p, normalize=True):
    pixels = p.pixel_array
    if not normalize:
        return pixels
    if normalize is True: # Map pixel values back to original HU values
        rescale_slope, rescale_intercept = get_rescale_params(p)
        return rescale_slope * pixels + rescale_intercept
    if isinstance(normalize, int):
        return (pixels + np.min(pixels)) / (np.max(pixels) - np.min(pixels)) * normalize
    if isinstance(normalize, list):
        return (pixels + np.min(pixels)) / (np.max(pixels) - np.min(pixels)) * normalize[1] + normalize[0]
    return pixels


def convert_dicom_to_numpy_array(dicom_file_path: str, window_level: int=50, window_width: int=400, normalize=True) -> np.array:
    p = pydicom.dcmread(dicom_file_path)
    pixels = p.pixel_array
    pixels = pixels.reshape(p.Rows, p.Columns)
    if normalize:
        b = p.RescaleIntercept
        m = p.RescaleSlope
        pixels = m * pixels + b
    pixels = apply_window_center_and_width(pixels, window_level, window_width)
    return pixels


def convert_dicom_to_png_image(dicom_file_path: str, output_dir_path: str, window_level: int=50, window_width: int=400, normalize=True) -> str:
    array = convert_dicom_to_numpy_array(dicom_file_path, window_level, window_width, normalize)
    convert_numpy_array_to_png_image(
        array,
        output_dir_path,
        None,
        os.path.split(dicom_file_path)[1] + '.png',
        10, 10,
    )