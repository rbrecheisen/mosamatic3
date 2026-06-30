import logging
import time
from collections.abc import Callable
from typing import Any

from config.celery_app import app
from .demo.service import run_demo_task
from .rescaledicomimages.service import run_rescale_dicom_images_task
from .sliceselect.service import run_slice_select_task
from .segmentmusclefatl3.service import run_segment_muscle_fat_l3_tensorflow_task
from .calculatescores.service import run_calculate_scores_task

logger = logging.getLogger(__name__)


def run_logged_task(
    *,
    celery_task,
    task_name: str,
    parameters: dict,
    user_id: str,
    func: Callable[..., dict],
) -> dict:
    task_id = getattr(celery_task.request, "id", None)
    start = time.monotonic()

    logger.info(
        "Task started: task_name=%s task_id=%s user_id=%s",
        task_name,
        task_id,
        user_id,
    )

    try:
        result = func(parameters, user_id, celery_task=celery_task)

        duration = time.monotonic() - start
        logger.info(
            "Task finished: task_name=%s task_id=%s user_id=%s duration_seconds=%.2f",
            task_name,
            task_id,
            user_id,
            duration,
        )

        return result

    except Exception:
        duration = time.monotonic() - start
        logger.exception(
            "Task failed: task_name=%s task_id=%s user_id=%s duration_seconds=%.2f",
            task_name,
            task_id,
            user_id,
            duration,
        )
        raise


@app.task(bind=True, name="core.processing.tasks.run_demotask")
def run_demotask(self, parameters: dict, user_id: str) -> dict:
    return run_logged_task(
        celery_task=self,
        task_name="run_demotask",
        parameters=parameters,
        user_id=user_id,
        func=run_demo_task,
    )


@app.task(bind=True, name="core.processing.tasks.run_rescaledicomimagestask")
def run_rescaledicomimagestask(self, parameters: dict, user_id: str) -> dict:
    return run_logged_task(
        celery_task=self,
        task_name="run_rescaledicomimagestask",
        parameters=parameters,
        user_id=user_id,
        func=run_rescale_dicom_images_task,
    )


@app.task(bind=True, name="core.processing.tasks.run_sliceselecttask")
def run_sliceselecttask(self, parameters: dict, user_id: str) -> dict:
    return run_logged_task(
        celery_task=self,
        task_name="run_sliceselecttask",
        parameters=parameters,
        user_id=user_id,
        func=run_slice_select_task,
    )


@app.task(bind=True, name="core.processing.tasks.run_segmentmusclefatl3tensorflowtask")
def run_segmentmusclefatl3tensorflowtask(self, parameters: dict, user_id: str) -> dict:
    return run_logged_task(
        celery_task=self,
        task_name="run_segmentmusclefatl3tensorflowtask",
        parameters=parameters,
        user_id=user_id,
        func=run_segment_muscle_fat_l3_tensorflow_task,
    )


@app.task(bind=True, name="core.processing.tasks.run_calculatescorestask")
def run_calculatescorestask(self, parameters: dict, user_id: str) -> dict:
    return run_logged_task(
        celery_task=self,
        task_name="run_calculatescorestask",
        parameters=parameters,
        user_id=user_id,
        func=run_calculate_scores_task,
    )

# from config.celery_app import app
# from .demo.service import run_demo_task
# from .rescaledicomimages.service import run_rescale_dicom_images_task
# from .sliceselect.service import run_slice_select_task
# from .segmentmusclefatl3.service import run_segment_muscle_fat_l3_tensorflow_task
# from .calculatescores.service import run_calculate_scores_task


# @app.task(bind=True, name='core.processing.tasks.run_demotask')
# def run_demotask(self, parameters: dict, user_id: str) -> dict:
#     return run_demo_task(parameters, user_id, celery_task=self)


# @app.task(bind=True, name='core.processing.tasks.run_rescaledicomimagestask')
# def run_rescaledicomimagestask(self, parameters: dict, user_id: str) -> dict:
#     return run_rescale_dicom_images_task(parameters, user_id, celery_task=self)


# @app.task(bind=True, name='core.processing.tasks.run_sliceselecttask')
# def run_sliceselecttask(self, parameters: dict, user_id: str) -> dict:
#     return run_slice_select_task(parameters, user_id, celery_task=self)


# @app.task(bind=True, name='core.processing.tasks.run_segmentmusclefatl3tensorflowtask')
# def run_segmentmusclefatl3tensorflowtask(self, parameters: dict, user_id: str) -> dict:
#     return run_segment_muscle_fat_l3_tensorflow_task(parameters, user_id, celery_task=self)


# @app.task(bind=True, name='core.processing.tasks.run_calculatescorestask')
# def run_calculatescorestask(self, parameters: dict, user_id: str) -> dict:
#     return run_calculate_scores_task(parameters, user_id, celery_task=self)