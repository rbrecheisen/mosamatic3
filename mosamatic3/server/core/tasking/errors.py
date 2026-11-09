"""Clear, file-specific failures shared across processing tasks and pipeline reports."""


class ProcessingInputError(ValueError):
    """An input cannot be processed as provided (shown to the dataset owner)."""


def require_single_grayscale_image(dicom, pixels, relative_path: str):
    """Fail before rescaling, inference or scoring on unsupported DICOM pixels.

    A single-frame monochrome CT image must decode to exactly (Rows, Columns).
    We deliberately do NOT squeeze a (1, H, W) multiframe image: that would
    silently change image semantics and could invalidate downstream analysis.
    """
    actual = tuple(pixels.shape)
    rows = getattr(dicom, 'Rows', None)
    columns = getattr(dicom, 'Columns', None)
    samples = getattr(dicom, 'SamplesPerPixel', None)
    frames = getattr(dicom, 'NumberOfFrames', 1) or 1
    expected = (rows, columns)
    if (len(actual) != 2 or actual != expected or samples != 1
            or str(frames) != '1'):
        raise ProcessingInputError(
            f'Unsupported DICOM image dimensions in "{relative_path}": '
            f'decoded pixel shape={actual}, Rows={rows}, Columns={columns}, '
            f'NumberOfFrames={frames}, SamplesPerPixel={samples}. '
            'Expected one 2D grayscale CT image (Rows x Columns) per file. '
            'Check whether the input is multiframe, color or otherwise not a single CT slice.'
        )
    return pixels


def decode_single_grayscale_image(dicom, relative_path: str):
    try:
        pixels = dicom.pixel_array
    except Exception as exc:
        raise ProcessingInputError(
            f'Cannot decode DICOM pixel data in "{relative_path}": '
            f'{type(exc).__name__}: {exc}. '
            'Check pixel encoding, Transfer Syntax UID and installed DICOM decoders.'
        ) from exc
    return require_single_grayscale_image(dicom, pixels, relative_path)


def describe_task_error(error, *, max_length: int = 1800) -> str:
    """A concise, non-traceback explanation for status pages and pipeline runs."""
    if isinstance(error, BaseException):
        name = type(error).__name__
        detail = str(error).strip()
    else:
        name = ''
        detail = str(error).strip()
    if not detail:
        detail = f'{name or "Processing"} failed without a detailed error message.'
    elif name and name not in ('ProcessingInputError', 'ValueError', 'RuntimeError'):
        detail = f'{name}: {detail}'
    return detail if len(detail) <= max_length else detail[:max_length - 3] + '...'
