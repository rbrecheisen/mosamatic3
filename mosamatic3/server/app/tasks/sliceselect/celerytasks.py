from app.celeryapp import celery_app
from app.tasks.sliceselect.service import run_sliceselect


@celery_app.task(
  bind=True,
  name="app.tasks.sliceselect.celerytasks.run_sliceselecttask",
)
def run_sliceselecttask(
  self,
  parameters: dict,
  user_id: str,
) -> dict:
  return run_sliceselect(
    parameters=parameters,
    user_id=user_id,
    celery_task=self,
  )