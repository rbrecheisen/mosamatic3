from app.celeryapp import celery_app
from app.tasks.rescaledicomimages.service import run_rescaledicomimages


@celery_app.task(
  bind=True,
  name="app.tasks.rescaledicomimages.celerytasks.run_rescaledicomimagestask",
)
def run_rescaledicomimagestask(
  self,
  parameters: dict,
  user_id: str,
) -> dict:
  return run_rescaledicomimages(
    parameters=parameters,
    user_id=user_id,
    celery_task=self,
  )