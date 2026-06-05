import json
import time
from typing import Any
from uuid import UUID
from sqlmodel import Session
from app.data.models import User
from app.data.database import engine
from app.services.datasetservice import (
  OutputDatasetFile,
  get_dataset_for_user,
  create_output_dataset_for_user_id,
)
from app.tasks.rescaledicomimages.schema import RescaleDicomImagesTaskParameters


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

  summary = {
    "message": "This is a generated output dataset from the rescale DICOM images task.",
    "input_dataset_id": str(params.dataset_id),
    "target_size": params.target_size,
    "overwrite_existing": params.overwrite_existing,
    "source_task_key": "rescaledicomimages",
    "source_task_id": task_id,
  }

  # Create output
  for iteration in range(nr_files):
    current_iteration = iteration + 1
    message = f"Rescale DICOM files iteration {current_iteration} of {nr_files}"
    print(message)

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
    time.sleep(0.25)


  # Create output dataset
  with Session(engine) as session:
    output_dataset = create_output_dataset_for_user_id(
      name="Rescale DICOM Images output",
      files=[
        OutputDatasetFile(
          relative_path="rescale_summary.json",
          content=json.dumps(summary, indent=2).encode("utf-8"),
        ),
      ],
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

  return {
    "current": 1,
    "total": 1,
    "message": "Rescale DICOM images task completed",
    "parameters": params.model_dump(mode="json"),
    "output_datasets": [
      output_dataset.model_dump(mode="json"),
    ],
  }