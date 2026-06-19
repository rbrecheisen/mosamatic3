import time
from io import BytesIO
import numpy as np
from scipy.ndimage import zoom
from celery.exceptions import Ignore
from ...common.dicom import load_dicom
from ...datasets.serializers import DatasetSerializer
from ...datasets.services import OutputDatasetFile
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import RescaleDicomImagesTaskParameters


def rescale_image(p, target_size):
    pixel_array = p.pixel_array
    hu_array = pixel_array * p.RescaleSlope + p.RescaleIntercept
    hu_air = -1000
    new_rows = max(p.Rows, p.Columns)
    padded_hu_array = np.full((new_rows, new_rows), hu_air, dtype=hu_array.dtype)
    padded_hu_array[:pixel_array.shape[0], :pixel_array.shape[1]] = hu_array
    pixel_array_padded = ((padded_hu_array - p.RescaleIntercept) / p.RescaleSlope).astype(pixel_array.dtype)
    pixel_array_rescaled = zoom(pixel_array_padded, zoom=(target_size / new_rows), order=3).astype(pixel_array.dtype)
    p.PixelSpacing = [ps * (new_rows / target_size) for ps in p.PixelSpacing]
    p.PixelData = pixel_array_rescaled.tobytes()
    p.Rows = target_size
    p.Columns = target_size
    return p


def process_dicom_file(file_path, relative_path: str, target_size: int) -> OutputDatasetFile | None:
    p = load_dicom(file_path)
    if p is None:
        return None
    if len(p.pixel_array.shape) != 2:
        print(f'Shape of pixel data should be 2D but is {p.pixel_array.shape}')
        return None
    if p.Rows != target_size or p.Columns != target_size:
        p = rescale_image(p, target_size)
    buffer = BytesIO()
    p.save_as(buffer)
    return OutputDatasetFile(relative_path=relative_path, content=buffer.getvalue())


def run_rescale_dicom_images_task(parameters: dict, user_id: str, celery_task=None) -> dict:
    runtime = TaskRuntime(task_key='rescaledicomimages', parameters=parameters, parameter_model=RescaleDicomImagesTaskParameters, user_id=user_id, celery_task=celery_task)
    params = runtime.params
    runtime.mark_running()
    try:
        dataset = runtime.get_input_dataset(params.dataset_id)
        total = dataset.files.count()
        runtime.update_progress(current=0, total=total, message='Starting DICOM rescaling')
        output_files = []
        for item in runtime.iter_dataset_files(dataset, message_factory=lambda current, total: f'Rescale DICOM files iteration {current} of {total}'):
            output_file = process_dicom_file(item.path, item.file.relative_path, params.target_size)
            if output_file is not None:
                output_files.append(output_file)
            time.sleep(0.05)
        output_dataset = runtime.create_output_dataset(name='Rescale DICOM Images output', files=output_files)
        runtime.update_progress(current=total, total=total, message='Finished DICOM rescaling')
        runtime.mark_finished()
        return {
            'current': total,
            'total': total,
            'message': 'Rescale DICOM images task completed',
            'parameters': params.model_dump(mode='json'),
            'output_datasets': [DatasetSerializer(output_dataset).data],
            'output_dataset_id': str(output_dataset.id),
        }
    except Ignore:
        raise
    except Exception:
        runtime.mark_failed()
        raise
