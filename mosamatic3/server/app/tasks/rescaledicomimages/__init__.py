from app.tasks.base import TaskDefinition
from app.tasks.rescaledicomimages.schema import RescaleDicomImagesTaskParameters


task_definition = TaskDefinition(
  key="rescaledicomimages",
  name="Rescale DICOM Images",
  description="Rescales DICOM images to a square dimension using zero-padding if necessary",
  celery_task_name="app.tasks.rescaledicomimages.celerytasks.run_rescaledicomimagestask",
  parameter_schema=RescaleDicomImagesTaskParameters,
)

# from app.tasks.base import TaskDefinition
# from app.tasks.rescaledicomimages.api import router
# from app.tasks.rescaledicomimages.schema import RescaleDicomImagesTaskParameters


# task_definition = TaskDefinition(
#   key="rescaledicomimages",
#   name="Rescale DICOM Images",
#   description="Rescales DICOM images to a square dimension using zero-padding if necessary",
#   router=router,
#   celery_task_name="app.tasks.demo.celerytasks.run_rescaledicomimagestask",
#   parameter_schema=RescaleDicomImagesTaskParameters,
# )