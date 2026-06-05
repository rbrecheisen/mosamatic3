from app.tasks.base import TaskDefinition
from app.tasks.sliceselect.schema import SliceSelectTaskParameters


task_definition = TaskDefinition(
  key="sliceselect",
  name="Select Slice From Scans",
  description="Selects single slices from a list of DICOM scans",
  celery_task_name="app.tasks.sliceselect.celerytasks.run_sliceselecttask",
  celery_module="app.tasks.sliceselect.celerytasks",
  parameter_schema=SliceSelectTaskParameters,
)