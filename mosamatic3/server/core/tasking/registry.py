from .definitions import TaskDefinition
from .schemas import (
  DemoTaskParameters, 
  RescaleDicomImagesTaskParameters,
  DecompressDicomFilesTaskParameters,
  SliceSelectTaskParameters,
  SegmentMuscleFatL3TensorFlowTaskParameters,
  CalculateScoresTaskParameters,
  CollectSingleCTImagesTaskParameters,
)

TASKS = {
  'demo': TaskDefinition(
      key='demo',
      name='Demo Task',
      description='Demonstrates task parameters and progress reporting',
      celery_task_name='core.processing.tasks.run_demotask',
      parameter_schema=DemoTaskParameters,
  ),
  'decompressdicomfiles': TaskDefinition(
      key='decompressdicomfiles',
      name='Decompress DICOM Files',
      description='Creates one output dataset with decompressed DICOM images, copying already uncompressed images unchanged and preserving filenames and paths',
      celery_task_name='core.processing.tasks.run_decompressdicomfilestask',
      parameter_schema=DecompressDicomFilesTaskParameters,
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
    description=
"""
Automatically selects an axial DICOM slice at a requested vertebral level using TotalSegmentator. 
Upload a single folder containing one or more subfolders for each patient, e.g., a folder "abdomen" that has
subfolders "patient1" and "patient2". The CT scan images must be in a single folder must can be nested further
down in the patient folder.
""",
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
  'collectsinglectimages': TaskDefinition(
    key="collectsinglectimages",
    name="Collect Single CT Images",
    description=(
        "Finds CT DICOM images below patient-specific folders "
        "and creates a flat output dataset with patient-based filenames"
    ),
    celery_task_name=(
        "core.processing.tasks.run_collectsinglectimagestask"
    ),
    parameter_schema=CollectSingleCTImagesTaskParameters,
  ),
}
