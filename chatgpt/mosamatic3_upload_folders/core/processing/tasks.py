from config.celery_app import app
from .demo.service import run_demo_task
from .rescaledicomimages.service import run_rescale_dicom_images_task
from .sliceselect.service import run_slice_select_task


@app.task(bind=True, name='core.processing.tasks.run_demotask')
def run_demotask(self, parameters: dict, user_id: str) -> dict:
    return run_demo_task(parameters, user_id, celery_task=self)


@app.task(bind=True, name='core.processing.tasks.run_rescaledicomimagestask')
def run_rescaledicomimagestask(self, parameters: dict, user_id: str) -> dict:
    return run_rescale_dicom_images_task(parameters, user_id, celery_task=self)


@app.task(bind=True, name='core.processing.tasks.run_sliceselecttask')
def run_sliceselecttask(self, parameters: dict, user_id: str) -> dict:
    return run_slice_select_task(parameters, user_id, celery_task=self)