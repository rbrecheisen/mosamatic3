from app.celeryapp import celery_app
from app.tasks.demo.service import run_demo_task


@celery_app.task(
  bind=True,
  name="app.tasks.demo.celerytasks.run_demotask",
)
def run_demotask(
  self,
  parameters: dict,
  user_id: str,
) -> dict:
  return run_demo_task(
    parameters=parameters,
    user_id=user_id,
    celery_task=self,
  )