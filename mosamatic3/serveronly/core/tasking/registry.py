from .definitions import TaskDefinition
from .schemas import (
  DemoTaskParameters, 
  RescaleDicomImagesTaskParameters,
  SliceSelectTaskParameters,
  SegmentMuscleFatL3TensorFlowTaskParameters,
  CalculateScoresTaskParameters,
)

TASKS = {
  'demo': TaskDefinition(
      key='demo',
      name='Demo Task',
      description='Demonstrates task parameters and progress reporting',
      celery_task_name='core.processing.tasks.run_demotask',
      parameter_schema=DemoTaskParameters,
  ),
  'rescaledicomimages': TaskDefinition(
      key='rescaledicomimages',
      name='Rescale DICOM Images',
      description='Rescales DICOM images to a square dimension using zero-padding if necessary',
      celery_task_name='core.processing.tasks.run_rescaledicomimagestask',
      parameter_schema=RescaleDicomImagesTaskParameters,
  ),
  'sliceselect': TaskDefinition(
    key='sliceselect',
    name='Slice Select',
    description='Automatically selects an axial DICOM slice at a requested vertebral level using TotalSegmentator',
    celery_task_name='core.processing.tasks.run_sliceselecttask',
    parameter_schema=SliceSelectTaskParameters,
  ),
  'segmentmusclefatl3tensorflow': TaskDefinition(
    key='segmentmusclefatl3tensorflow',
    name='Segment Muscle/Fat L3 TensorFlow',
    description='Segments muscle and fat tissue on selected L3 DICOM slices using TensorFlow models',
    celery_task_name='core.processing.tasks.run_segmentmusclefatl3tensorflowtask',
    parameter_schema=SegmentMuscleFatL3TensorFlowTaskParameters,
  ),
  'calculatescores': TaskDefinition(
    key='calculatescores',
    name='Calculate Scores',
    description='Calculates body-composition scores from DICOM images and muscle/fat segmentations',
    celery_task_name='core.processing.tasks.run_calculatescorestask',
    parameter_schema=CalculateScoresTaskParameters,
  ),
}
