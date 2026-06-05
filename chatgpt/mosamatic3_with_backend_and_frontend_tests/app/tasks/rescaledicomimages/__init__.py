from app.tasks.base import TaskDefinition
from app.tasks.rescaledicomimages.schema import RescaleDicomImagesTaskParameters


task_definition = TaskDefinition(
  key="rescaledicomimages",
  name="Rescale DICOM Images",
  description="Rescales DICOM images to a square dimension using zero-padding if necessary",
  celery_task_name="app.tasks.rescaledicomimages.celerytasks.run_rescaledicomimagestask",
  celery_module="app.tasks.rescaledicomimages.celerytasks",
  parameter_schema=RescaleDicomImagesTaskParameters,
)