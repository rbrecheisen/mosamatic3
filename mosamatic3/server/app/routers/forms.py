from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from ..services.authservice import get_current_user
from ..data.database import get_session
from ..data.models import FormSubmission, User
from ..data.schemas import FormSubmissionCreate, FormSubmissionRead
from ..services.formservice import create_submission, list_submissions

router = APIRouter()


@router.post("", response_model=FormSubmissionRead, status_code=status.HTTP_201_CREATED)
def create_form_submission(
  payload: FormSubmissionCreate,
  current_user: User = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> FormSubmission:
  return create_submission(payload, current_user, session)


@router.get("", response_model=list[FormSubmissionRead])
def list_form_submissions(
  current_user: User = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> list[FormSubmission]:
  return list_submissions(current_user, session)