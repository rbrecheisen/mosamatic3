from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from ..services.authservice import get_current_admin_user
from ..data.database import get_session
from ..data.models import User
from ..data.schemas import AdminDatasetRead, AdminSummary, AdminUserRead
from ..services.adminservice import (
  block_user,
  delete_user,
  get_admin_summary,
  list_admin_datasets,
  list_admin_users,
  unblock_user,
)

router = APIRouter()


@router.get("/summary", response_model=AdminSummary)
def admin_summary(
  _: User = Depends(get_current_admin_user),
  session: Session = Depends(get_session),
) -> AdminSummary:
  return get_admin_summary(session)


@router.get("/users", response_model=list[AdminUserRead])
def admin_list_users(
  _: User = Depends(get_current_admin_user),
  session: Session = Depends(get_session),
) -> list[User]:
  return list_admin_users(session)


@router.get("/datasets", response_model=list[AdminDatasetRead])
def admin_list_datasets(
  _: User = Depends(get_current_admin_user),
  session: Session = Depends(get_session),
) -> list[AdminDatasetRead]:
  return list_admin_datasets(session)


@router.patch("/users/{user_id}/block", response_model=AdminUserRead)
def admin_block_user(
  user_id: UUID,
  current_admin: User = Depends(get_current_admin_user),
  session: Session = Depends(get_session),
) -> User:
  return block_user(user_id, current_admin, session)


@router.patch("/users/{user_id}/unblock", response_model=AdminUserRead)
def admin_unblock_user(
  user_id: UUID,
  current_admin: User = Depends(get_current_admin_user),
  session: Session = Depends(get_session),
) -> User:
  return unblock_user(user_id, current_admin, session)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
  user_id: UUID,
  current_admin: User = Depends(get_current_admin_user),
  session: Session = Depends(get_session),
) -> None:
  delete_user(user_id, current_admin, session)