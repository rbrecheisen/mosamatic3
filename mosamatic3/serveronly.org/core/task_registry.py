from .task_base import TaskDefinition
from .task_schemas import DemoTaskParameters, RescaleDicomImagesTaskParameters

TASKS = {
    'demo': TaskDefinition(
        key='demo',
        name='Demo Task',
        description='Demonstrates task parameters and progress reporting',
        celery_task_name='core.tasks.run_demotask',
        parameter_schema=DemoTaskParameters,
    ),
    'rescaledicomimages': TaskDefinition(
        key='rescaledicomimages',
        name='Rescale DICOM Images',
        description='Rescales DICOM images to a square dimension using zero-padding if necessary',
        celery_task_name='core.tasks.run_rescaledicomimagestask',
        parameter_schema=RescaleDicomImagesTaskParameters,
    ),
}
