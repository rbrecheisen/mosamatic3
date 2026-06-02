import json
from typing import Any
from uuid import UUID
from sqlmodel import Session

from app.data.database import engine
from app.services.datasetservice import (
  OutputDatasetFile,
  create_output_dataset_for_user_id,
)
from app.tasks.rescaledicomimages.schema import RescaleDicomImagesTaskParameters


def run_rescaledicomimages(
  parameters: dict,
  user_id: str,
  celery_task: Any | None = None,
) -> dict:
  params = RescaleDicomImagesTaskParameters.model_validate(parameters)
  if celery_task is not None:
    celery_task.update_state(
      state="PROGRESS",
      meta={
        "current": 0,
        "total": 1,
        "message": "Starting DICOM rescaling",
      },
    )

  print("Rescale DICOM images")
  print("User ID:", user_id)
  print("Dataset ID:", params.dataset_id)
  for dataset_id in params.dataset_ids:
    print("Listed dataset ID:", dataset_id)
  print("Target size:", params.target_size)
  print("Overwrite existing:", params.overwrite_existing)

  task_id = None
  if celery_task is not None and getattr(celery_task, "request", None) is not None:
    task_id = celery_task.request.id
  summary = {
    "message": "This is a generated output dataset from the rescale DICOM images task.",
    "input_dataset_id": str(params.dataset_id),
    "input_dataset_ids": [str(dataset_id) for dataset_id in params.dataset_ids],
    "target_size": params.target_size,
    "overwrite_existing": params.overwrite_existing,
    "source_task_key": "rescaledicomimages",
    "source_task_id": task_id,
  }
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
        "current": 1,
        "total": 1,
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

# from typing import Any
# from app.tasks.rescaledicomimages.schema import RescaleDicomImagesTaskParameters


# def run_rescaledicomimages(
#   parameters: dict,
#   user_id: str,
#   celery_task: Any | None = None,
# ) -> dict:
#   params = RescaleDicomImagesTaskParameters.model_validate(parameters)
#   if celery_task is not None:
#     celery_task.update_state(
#       state="PROGRESS",
#       meta={
#         "current": 0,
#         "total": 1,
#         "message": "Starting DICOM rescaling",
#       },
#     )
#   print("Rescale DICOM images")
#   print("User ID:", user_id)
#   print("Dataset ID:", params.dataset_id)
#   for dataset_id in params.dataset_ids:
#     print("Listed dataset ID: ", dataset_id)
#   print("Target size:", params.target_size)
#   print("Overwrite existing:", params.overwrite_existing)

#   # TODO:
#   # 1. Locate dataset folder
#   # 2. Iterate DICOM files
#   # 3. Read with pydicom
#   # 4. Rescale / pad pixel array
#   # 5. Save output files

#   if celery_task is not None:
#     celery_task.update_state(
#       state="PROGRESS",
#       meta={
#         "current": 1,
#         "total": 1,
#         "message": "Finished DICOM rescaling",
#       },
#     )
#   return {
#     "current": 1,
#     "total": 1,
#     "message": "Rescale DICOM images task completed",
#     "parameters": params.model_dump(mode="json"),
#   }