from pathlib import Path, PurePosixPath

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from .auth import authenticate_user, create_access_token, get_current_user, hash_password
from .config import settings
from .database import create_db_and_tables, get_session
from .models import Dataset, DatasetFile, FormSubmission, User
from .schemas import (
    DatasetFileRead,
    DatasetRead,
    FormSubmissionCreate,
    FormSubmissionRead,
    Token,
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


def dataset_to_read(dataset: Dataset, files: list[DatasetFile]) -> DatasetRead:
    return DatasetRead(
        id=dataset.id,
        name=dataset.name,
        created_at=dataset.created_at,
        file_count=len(files),
        total_size_bytes=sum(file.size_bytes for file in files),
        files=[
            DatasetFileRead(
                id=file.id,
                relative_path=file.relative_path,
                size_bytes=file.size_bytes,
                created_at=file.created_at,
            )
            for file in files
        ],
    )


@app.post("/api/datasets", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    name: str = Form(...),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DatasetRead:
    dataset_name = name.strip()
    if not dataset_name:
        raise HTTPException(status_code=400, detail="Dataset name is required")
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    existing = session.exec(
        select(Dataset).where(
            Dataset.owner_id == current_user.id,
            Dataset.name == dataset_name,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A dataset with this name already exists")

    dataset = Dataset(owner_id=current_user.id, name=dataset_name)
    session.add(dataset)

    dataset_upload_root = settings.upload_root / str(current_user.id) / str(dataset.id)
    dataset_upload_root.mkdir(parents=True, exist_ok=False)

    dataset_files: list[DatasetFile] = []
    for upload in files:
        relative_path = safe_relative_path(upload.filename or "uploaded_file")
        target_path = dataset_upload_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        size_bytes = 0
        with target_path.open("wb") as out_file:
            while chunk := await upload.read(1024 * 1024):
                size_bytes += len(chunk)
                out_file.write(chunk)

        dataset_file = DatasetFile(
            dataset_id=dataset.id,
            relative_path=relative_path.as_posix(),
            size_bytes=size_bytes,
        )
        session.add(dataset_file)
        dataset_files.append(dataset_file)

    session.commit()
    session.refresh(dataset)
    for dataset_file in dataset_files:
        session.refresh(dataset_file)

    return dataset_to_read(dataset, dataset_files)


@app.get("/api/datasets", response_model=list[DatasetRead])
def list_datasets(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[DatasetRead]:
    datasets = session.exec(
        select(Dataset)
        .where(Dataset.owner_id == current_user.id)
        .order_by(Dataset.created_at.desc())
    ).all()

    result: list[DatasetRead] = []
    for dataset in datasets:
        files = list(
            session.exec(
                select(DatasetFile)
                .where(DatasetFile.dataset_id == dataset.id)
                .order_by(DatasetFile.relative_path)
            )
        )
        result.append(dataset_to_read(dataset, files))
    return result


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
