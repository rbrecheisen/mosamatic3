from typing import Any
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
    print("Listed dataset ID: ", dataset_id)
  print("Target size:", params.target_size)
  print("Overwrite existing:", params.overwrite_existing)

  # TODO:
  # 1. Locate dataset folder
  # 2. Iterate DICOM files
  # 3. Read with pydicom
  # 4. Rescale / pad pixel array
  # 5. Save output files

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
  }

# import time
# from app.tasks.rescaledicomimages.schema import RescaleDicomImagesTaskParameters


# def run_rescaledicomimages(parameters: dict, user_id: int):
#   params = RescaleDicomImagesTaskParameters.model_validate(parameters)
#   time.sleep(params.seconds)
#   return {
#     "message": f"RescaleDicomImagesTask finished after {params.seconds} seconds",
#     "user_id": user_id,
#   }