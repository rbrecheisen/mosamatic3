import time
import numpy as np
from io import BytesIO
from typing import Any
from scipy.ndimage import zoom
from celery.exceptions import Ignore
from app.utils import load_dicom
from app.tasks.runtime import TaskRuntime
from app.services.datasetservice import OutputDatasetFile
from app.tasks.rescaledicomimages.schema import RescaleDicomImagesTaskParameters


def rescale_image(p, target_size):
  pixel_array = p.pixel_array
  hu_array = pixel_array * p.RescaleSlope + p.RescaleIntercept
  hu_air = -1000
  new_rows = max(p.Rows, p.Columns)
  new_cols = max(p.Rows, p.Columns)
  padded_hu_array = np.full((new_rows, new_cols), hu_air, dtype=hu_array.dtype)
  padded_hu_array[:pixel_array.shape[0], :pixel_array.shape[1]] = hu_array
  pixel_array_padded = (padded_hu_array - p.RescaleIntercept) / p.RescaleSlope
  pixel_array_padded = pixel_array_padded.astype(pixel_array.dtype)
  pixel_array_rescaled = zoom(
    pixel_array_padded,
    zoom=(target_size / new_rows),
    order=3,
  )
  pixel_array_rescaled = pixel_array_rescaled.astype(pixel_array.dtype)
  original_pixel_spacing = p.PixelSpacing
  new_pixel_spacing = [
    ps * (new_rows / target_size)
    for ps in original_pixel_spacing
  ]
  p.PixelSpacing = new_pixel_spacing
  p.PixelData = pixel_array_rescaled.tobytes()
  p.Rows = target_size
  p.Columns = target_size
  return p


def process_dicom_file(file_path, relative_path: str, target_size: int) -> OutputDatasetFile | None:
  p = load_dicom(file_path)
  if p is None:
    print(f"Could not load DICOM file {file_path}")
    return None
  if len(p.pixel_array.shape) != 2:
    print(f"Shape of pixel data should be 2D but is {p.pixel_array.shape}")
    return None
  if p.Rows != target_size or p.Columns != target_size:
    p = rescale_image(p, target_size)
  buffer = BytesIO()
  p.save_as(buffer)
  return OutputDatasetFile(
    relative_path=relative_path,
    content=buffer.getvalue(),
  )


def run_rescaledicomimages(
  parameters: dict,
  user_id: str,
  celery_task: Any | None = None,
) -> dict:
  
  # Create new task runtime
  runtime = TaskRuntime(
    task_key="rescaledicomimages",
    parameters=parameters,
    parameter_model=RescaleDicomImagesTaskParameters,
    user_id=user_id,
    celery_task=celery_task,
  )

  # Get runtime parameters and values
  params = runtime.params

  # Mark task as running
  runtime.mark_running()

  try:

    # Get input dataset and total file count
    dataset = runtime.get_input_dataset(params.dataset_id)
    total = dataset.file_count

    # Update runtime progress to start at zero
    runtime.update_progress(
      current=0,
      total=total,
      message="Starting DICOM rescaling",
    )

    # Create empty output file list
    output_files: list[OutputDatasetFile] = []

    # Run through the list of input files
    for item in runtime.iter_dataset_files(
      dataset,
      message_factory=lambda current, total: (
        f"Rescale DICOM files iteration {current} of {total}"
      ),
    ):
      
      # Process the current input file and add its result to the output list
      output_file = process_dicom_file(
        file_path=item.path,
        relative_path=item.file.relative_path,
        target_size=params.target_size,
      )
      if output_file is not None:
        output_files.append(output_file)
      time.sleep(0.05)

    # Create new output dataset with the output files
    output_dataset = runtime.create_output_dataset(
      name="Rescale DICOM Images output",
      files=output_files,
    )

    # Update runtime progress to finish
    runtime.update_progress(
      current=total,
      total=total,
      message="Finished DICOM rescaling",
    )

    # Mark task status as finished
    runtime.mark_finished()

    # Return task result meta data
    return {
      "current": total,
      "total": total,
      "message": "Rescale DICOM images task completed",
      "parameters": params.model_dump(mode="json"),
      "output_datasets": [
        output_dataset.model_dump(mode="json"),
      ],
    }
  except Ignore:
    raise
  except Exception:
    runtime.mark_failed()
    raise