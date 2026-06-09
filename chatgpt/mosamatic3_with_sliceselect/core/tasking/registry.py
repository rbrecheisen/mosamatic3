from .definitions import TaskDefinition
from .schemas import DemoTaskParameters, RescaleDicomImagesTaskParameters, SliceSelectTaskParameters

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
}

