from pathlib import Path, PurePosixPath

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from .auth import authenticate_user, create_access_token, get_current_user, hash_password
from .config import settings
from .database import create_db_and_tables, get_session
from .models import FormSubmission, User
from .schemas import (
    FormSubmissionCreate,
    FormSubmissionRead,
    Token,
    UploadResult,
    UserCreate,
    UserRead,
)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: Session = Depends(get_session)) -> User:
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.post("/api/auth/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> Token:
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return Token(access_token=create_access_token(user.email))


@app.get("/api/auth/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def safe_relative_path(filename: str) -> Path:
    """Allow browser directory uploads while blocking ../ path traversal."""
    posix_path = PurePosixPath(filename.replace("\\", "/"))
    parts = [part for part in posix_path.parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise HTTPException(status_code=400, detail=f"Unsafe filename: {filename}")
    return Path(*parts)


@app.post("/api/uploads", response_model=UploadResult)
async def upload_files(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
) -> UploadResult:
    user_upload_root = settings.upload_root / str(current_user.id)
    user_upload_root.mkdir(parents=True, exist_ok=True)

    saved_files: list[str] = []
    for upload in files:
        relative_path = safe_relative_path(upload.filename or "uploaded_file")
        target_path = user_upload_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with target_path.open("wb") as out_file:
            while chunk := await upload.read(1024 * 1024):
                out_file.write(chunk)

        saved_files.append(str(target_path.relative_to(settings.upload_root)))

    return UploadResult(saved_files=saved_files)


@app.post("/api/forms", response_model=FormSubmissionRead, status_code=status.HTTP_201_CREATED)
def create_form_submission(
    payload: FormSubmissionCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> FormSubmission:
    submission = FormSubmission(owner_id=current_user.id, **payload.model_dump())
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission


@app.get("/api/forms", response_model=list[FormSubmissionRead])
def list_form_submissions(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[FormSubmission]:
    return list(
        session.exec(
            select(FormSubmission)
            .where(FormSubmission.owner_id == current_user.id)
            .order_by(FormSubmission.created_at.desc())
        )
    )
