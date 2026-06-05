from uuid import UUID
from sqlmodel import Session, select
from app.data.database import engine
from app.data.models import TaskRun, User, utc_now


def create_task_run(
  *,
  owner_id: UUID,
  task_key: str,
  celery_task_id: str,
  session: Session,
) -> TaskRun:
  task_run = TaskRun(
    owner_id=owner_id,
    task_key=task_key,
    celery_task_id=celery_task_id,
    status="queued",
    cancel_requested=False,
  )
  session.add(task_run)
  session.commit()
  session.refresh(task_run)
  return task_run


def request_task_cancel(
  *,
  celery_task_id: str,
  current_user: User,
  session: Session,
) -> TaskRun | None:
  task_run = session.exec(
    select(TaskRun).where(
      TaskRun.owner_id == current_user.id,
      TaskRun.celery_task_id == celery_task_id,
    )
  ).first()

  if task_run is None:
    return None

  task_run.cancel_requested = True
  task_run.status = "cancel_requested"
  task_run.updated_at = utc_now()
  session.add(task_run)
  session.commit()
  session.refresh(task_run)
  return task_run


def is_cancel_requested(celery_task_id: str | None) -> bool:
  if celery_task_id is None:
    return False

  with Session(engine) as session:
    task_run = session.exec(
      select(TaskRun).where(TaskRun.celery_task_id == celery_task_id)
    ).first()

    return bool(task_run and task_run.cancel_requested)


def mark_task_run_status(
  celery_task_id: str | None,
  status: str,
) -> None:
  if celery_task_id is None:
    return

  with Session(engine) as session:
    task_run = session.exec(
      select(TaskRun).where(TaskRun.celery_task_id == celery_task_id)
    ).first()

    if task_run is None:
      return

    task_run.status = status
    task_run.updated_at = utc_now()
    session.add(task_run)
    session.commit()