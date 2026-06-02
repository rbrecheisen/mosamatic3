from sqlmodel import Session, select
from ..data.models import FormSubmission, User
from ..data.schemas import FormSubmissionCreate


def create_submission(
    payload: FormSubmissionCreate,
    current_user: User,
    session: Session,
) -> FormSubmission:
    submission = FormSubmission(
        owner_id=current_user.id,
        **payload.model_dump(),
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission


def list_submissions(
    current_user: User,
    session: Session,
) -> list[FormSubmission]:
    return list(
        session.exec(
            select(FormSubmission)
            .where(FormSubmission.owner_id == current_user.id)
            .order_by(FormSubmission.created_at.desc())
        )
    )