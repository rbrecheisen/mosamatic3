import shutil
from uuid import UUID
from fastapi import HTTPException
from sqlmodel import Session, select
from ..config import settings
from ..data.models import Dataset, DatasetFile, FormSubmission, User
from ..data.schemas import AdminDatasetRead, AdminSummary


def get_admin_target_user(
    user_id: UUID,
    current_admin: User,
    session: Session,
) -> User:
    target_user = session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target_user.id == current_admin.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot modify your own admin account here",
        )
    if target_user.email == settings.admin_username:
        raise HTTPException(
            status_code=400,
            detail="The built-in admin user cannot be modified here",
        )
    return target_user


def get_admin_summary(session: Session) -> AdminSummary:
    users = session.exec(select(User)).all()
    datasets = session.exec(select(Dataset)).all()
    dataset_files = session.exec(select(DatasetFile)).all()
    return AdminSummary(
        user_count=len(users),
        dataset_count=len(datasets),
        dataset_file_count=len(dataset_files),
    )


def list_admin_users(session: Session) -> list[User]:
    return list(session.exec(select(User).order_by(User.created_at.desc())))


def list_admin_datasets(session: Session) -> list[AdminDatasetRead]:
    datasets = session.exec(
        select(Dataset).order_by(Dataset.created_at.desc())
    ).all()
    result: list[AdminDatasetRead] = []
    for dataset in datasets:
        files = list(
            session.exec(
                select(DatasetFile).where(DatasetFile.dataset_id == dataset.id)
            )
        )
        result.append(
            AdminDatasetRead(
                id=dataset.id,
                name=dataset.name,
                owner_id=dataset.owner_id,
                created_at=dataset.created_at,
                file_count=len(files),
                total_size_bytes=sum(file.size_bytes for file in files),
            )
        )
    return result


def block_user(
    user_id: UUID,
    current_admin: User,
    session: Session,
) -> User:
    target_user = get_admin_target_user(user_id, current_admin, session)
    target_user.is_active = False
    session.add(target_user)
    session.commit()
    session.refresh(target_user)
    return target_user


def unblock_user(
    user_id: UUID,
    current_admin: User,
    session: Session,
) -> User:
    target_user = get_admin_target_user(user_id, current_admin, session)
    target_user.is_active = True
    session.add(target_user)
    session.commit()
    session.refresh(target_user)
    return target_user


def delete_user(
    user_id: UUID,
    current_admin: User,
    session: Session,
) -> None:
    target_user = get_admin_target_user(user_id, current_admin, session)
    datasets = session.exec(
        select(Dataset).where(Dataset.owner_id == target_user.id)
    ).all()
    for dataset in datasets:
        dataset_files = session.exec(
            select(DatasetFile).where(DatasetFile.dataset_id == dataset.id)
        ).all()
        for dataset_file in dataset_files:
            session.delete(dataset_file)
        session.delete(dataset)
        dataset_upload_root = (
            settings.upload_root / str(target_user.id) / str(dataset.id)
        )
        shutil.rmtree(dataset_upload_root, ignore_errors=True)
    form_submissions = session.exec(
        select(FormSubmission).where(FormSubmission.owner_id == target_user.id)
    ).all()
    for form_submission in form_submissions:
        session.delete(form_submission)
    session.delete(target_user)
    session.commit()