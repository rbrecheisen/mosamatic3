import time
import numpy as np
from io import BytesIO
from typing import Any
from uuid import UUID
from scipy.ndimage import zoom
from sqlmodel import Session
from celery.exceptions import Ignore
from app.data.models import User
from app.data.database import engine
from app.utils import (
  load_dicom,
)
from app.tasks.rescaledicomimages.schema import RescaleDicomImagesTaskParameters
from app.services.taskrunservice import is_cancel_requested, mark_task_run_status
from app.services.datasetservice import (
  OutputDatasetFile,
  get_dataset_file_path,
  get_dataset_for_user,
  create_output_dataset_for_user_id,
)


def rescale_image(p, target_size):
  pixel_array = p.pixel_array
  hu_array = pixel_array * p.RescaleSlope + p.RescaleIntercept
  hu_air = -1000
  new_rows = max(p.Rows, p.Columns)
  new_cols = max(p.Rows, p.Columns)
  padded_hu_array = np.full((new_rows, new_cols), hu_air, dtype=hu_array.dtype)
  padded_hu_array[:pixel_array.shape[0], :pixel_array.shape[1]] = hu_array
  pixel_array_padded = (padded_hu_array - p.RescaleIntercept) / p.RescaleSlope
  pixel_array_padded = pixel_array_padded.astype(pixel_array.dtype) # Image now has largest dimensions
  pixel_array_rescaled = zoom(pixel_array_padded, zoom=(target_size / new_rows), order=3) # Cubic interpolation
  pixel_array_rescaled = pixel_array_rescaled.astype(pixel_array.dtype)
  original_pixel_spacing = p.PixelSpacing
  new_pixel_spacing = [ps * (new_rows / target_size) for ps in original_pixel_spacing]
  p.PixelSpacing = new_pixel_spacing
  p.PixelData = pixel_array_rescaled.tobytes()
  p.Rows = target_size
  p.Columns = target_size
  return p


def run_rescaledicomimages(
  parameters: dict,
  user_id: str,
  celery_task: Any | None = None,
) -> dict:
  
  # Validate parameters for this task
  params = RescaleDicomImagesTaskParameters.model_validate(parameters)

  # Convert string-based user ID to UUID before retrieving user from database
  user_uuid = UUID(user_id)

  # Open up session and get user + dataset
  with Session(engine) as session:
    user = session.get(User, user_uuid)
    if user is None:
      raise ValueError(f"User not found: {user_id}")
    dataset = get_dataset_for_user(params.dataset_id, user, session)
    nr_files = dataset.file_count
    print(f"Nr. files in input dataset: {nr_files}")

  # Initialize task state
  if celery_task is not None:
    celery_task.update_state(
      state="PROGRESS",
      meta={
        "current": 0,
        "total": nr_files,
        "message": "Starting DICOM rescaling",
      },
    )

  print("Rescale DICOM images")
  print(f"User ID: {user_id}")
  print(f"Dataset ID: {params.dataset_id}")
  print(f"Target size: {params.target_size}")
  print(f"Overwrite existing: {params.overwrite_existing}")

  task_id = None
  if celery_task is not None and getattr(celery_task, "request", None) is not None:
    task_id = celery_task.request.id

  # Create empty output dataset
  output_files: list[OutputDatasetFile] = []

  # Process each file in the input dataset and store in output set
  for iteration in range(nr_files):

    # Check if task was cancelled
    if is_cancel_requested(task_id):
      message = f"Rescale DICOM images task cancelled after {iteration} of {nr_files} files"
      print(message)
      mark_task_run_status(task_id, "cancelled")
      if celery_task is not None:
        celery_task.update_state(
          state="REVOKED",
          meta={
            "current": iteration,
            "total": nr_files,
            "message": message,
          },
        )
      raise Ignore()
  
    current_iteration = iteration + 1
    message = f"Rescale DICOM files iteration {current_iteration} of {nr_files}"
    print(message)

    # Get file object in dataset
    file = dataset.files[iteration]
    file_path = get_dataset_file_path(
      user_id=user_uuid,
      dataset_id=dataset.id,
      relative_path=file.relative_path,
    )

    # Rescale the file if possible/needed
    p_rescaled = None
    p = load_dicom(file_path)
    if p is not None:
      if len(p.pixel_array.shape) == 2:
        if p.Rows != params.target_size or p.Columns != params.target_size:
          p_rescaled = rescale_image(p, params.target_size)
        else:
          p_rescaled = p
      else:
        print(f"Shape of pixel data should be 2D but is {p.pixel_array.shape}")
      
      # Save rescaled image as output file
      if p_rescaled is not None:
        buffer = BytesIO()
        p_rescaled.save_as(buffer)
        p_rescaled_bytes = buffer.getvalue()
        output_files.append(
          OutputDatasetFile(
            relative_path=file.relative_path,
            content=p_rescaled_bytes,
          )
        )
      else:
        print(f"Failed to rescale DICOM image (result is None)")
    else:
      print(f"Could not load DICOM file {file_path}")

    # Update task status for this iteration
    if celery_task is not None:
      celery_task.update_state(
        state="PROGRESS",
        meta={
          "current": current_iteration,
          "total": nr_files,
          "message": message,
        },
      )
    time.sleep(0.05)

  # Create output dataset
  with Session(engine) as session:
    output_dataset = create_output_dataset_for_user_id(
      name="Rescale DICOM Images output",
      files=output_files,
      user_id=UUID(user_id),
      session=session,
      source_task_key="rescaledicomimages",
      source_task_id=task_id,
    )

  if celery_task is not None:
    celery_task.update_state(
      state="PROGRESS",
      meta={
        "current": nr_files,
        "total": nr_files,
        "message": "Finished DICOM rescaling",
      },
    )

  mark_task_run_status(task_id, "finished")

  return {
    "current": 1,
    "total": 1,
    "message": "Rescale DICOM images task completed",
    "parameters": params.model_dump(mode="json"),
    "output_datasets": [
      output_dataset.model_dump(mode="json"),
    ],
  }