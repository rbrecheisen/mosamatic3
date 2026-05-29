from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from ..data.database import get_session
from ..data.models import User
from ..data.schemas import TaskParametersRead, TaskParametersSave
from ..services.authservice import get_current_user
from ..services.taskservice import (
    get_celery_task_status,
    get_saved_task_parameters,
    save_task_parameters,
    start_demotask,
    start_rescaledicomimagestask,
    start_task_by_key,
)

router = APIRouter()


# @router.post("/demo", status_code=status.HTTP_202_ACCEPTED)
# def demotask(
#     seconds: int = Query(default=5, ge=1, le=300),
#     _: User = Depends(get_current_user),
# ) -> dict[str, str]:
#     return start_demotask(seconds)


# @router.post("/rescaledicomimages", status_code=status.HTTP_202_ACCEPTED)
# def rescaledicomimagestask(
#     _: User = Depends(get_current_user),
# ) -> dict[str, str]:
#     return start_rescaledicomimagestask()


@router.get("/{task_key}/parameters", response_model=TaskParametersRead)
def read_task_parameters(
    task_key: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TaskParametersRead:
    return get_saved_task_parameters(task_key, current_user, session)


@router.post("/{task_key}/parameters", response_model=TaskParametersRead)
def update_task_parameters(
    task_key: str,
    payload: TaskParametersSave,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TaskParametersRead:
    return save_task_parameters(task_key, payload, current_user, session)


@router.post("/{task_key}/run", status_code=status.HTTP_202_ACCEPTED)
def run_task(
    task_key: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    return start_task_by_key(task_key, current_user, session)


@router.get("/{task_id}")
def get_task_status(
    task_id: str,
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    return get_celery_task_status(task_id)

# from fastapi import APIRouter, Depends, Query, status
# from ..services.authservice import get_current_user
# from ..data.models import User
# from ..services.taskservice import (
#   get_celery_task_status, 
#   start_demotask,
#   start_rescaledicomimagestask,
# )

# router = APIRouter()


# @router.post("/demo", status_code=status.HTTP_202_ACCEPTED)
# def demotask(
#     seconds: int = Query(default=5, ge=1, le=300),
#     _: User = Depends(get_current_user),
# ) -> dict[str, str]:
#     return start_demotask(seconds)


# @router.post("/rescaledicomimages", status_code=status.HTTP_202_ACCEPTED)
# def rescaledicomimagestask() -> dict[str, str]:
#     return start_rescaledicomimagestask()


# @router.get("/{task_id}")
# def get_task_status(
#     task_id: str,
#     _: User = Depends(get_current_user),
# ) -> dict[str, object]:
#     return get_celery_task_status(task_id)