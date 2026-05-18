from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .startup import on_startup
from .routers import auth, admin, datasets, forms, tasks, health

@asynccontextmanager
async def lifespan(app: FastAPI):
    on_startup()
    yield

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(forms.router, prefix="/api/forms", tags=["forms"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])

# import shutil
# from uuid import UUID
# from pathlib import Path, PurePosixPath
# from celery.result import AsyncResult
# from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status, Query
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlmodel import Session, select
# from .auth import authenticate_user, create_access_token, get_current_user, get_current_admin_user, hash_password
# from .config import settings
# from .database import create_db_and_tables, engine, get_session
# from .models import Dataset, DatasetFile, FormSubmission, User
# from .tasks import demo_background_task
# from .processing import celery_app
# from .schemas import (
#     DatasetFileRead,
#     DatasetRead,
#     FormSubmissionCreate,
#     FormSubmissionRead,
#     Token,
#     UserCreate,
#     UserRead,
#     AdminSummary,
#     AdminDatasetRead,
#     AdminUserRead,
# )

# app = FastAPI(title=settings.app_name)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[settings.frontend_origin],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# def read_admin_password() -> str:
#     password_file = settings.admin_password_file
#     if not password_file.exists():
#         # raise RuntimeError(...)
#         raise RuntimeError('File with admin password does not exist')
#     password = password_file.read_text(encoding="utf-8").strip()
#     if not password:
#         # raise RuntimeError(...)
#         raise RuntimeError('Could not load admin password')
#     return password


# def ensure_admin_user() -> None:
#     admin_password = read_admin_password()
#     with Session(engine) as session:
#         admin = session.exec(
#             select(User).where(User.email == settings.admin_username)
#         ).first()
#         admin_hash = hash_password(admin_password)
#         if admin is None:
#             admin = User(
#                 email=settings.admin_username,
#                 hashed_password=admin_hash,
#                 is_admin=True,
#             )
#             session.add(admin)
#         else:
#             admin.hashed_password = admin_hash
#             admin.is_admin = True
#             admin.is_active = True
#             session.add(admin)
#         session.commit()


# def get_admin_target_user(
#     user_id: UUID,
#     current_admin: User,
#     session: Session,
# ) -> User:
#     target_user = session.get(User, user_id)
#     if target_user is None:
#         raise HTTPException(status_code=404, detail="User not found")
#     if target_user.id == current_admin.id:
#         raise HTTPException(
#             status_code=400,
#             detail="You cannot modify your own admin account here",
#         )
#     if target_user.email == settings.admin_username:
#         raise HTTPException(
#             status_code=400,
#             detail="The built-in admin user cannot be modified here",
#         )
#     return target_user


# @app.on_event("startup")
# def on_startup() -> None:
#     create_db_and_tables()
#     ensure_admin_user()


# @app.get("/api/health")
# def health() -> dict[str, str]:
#     return {"status": "ok"}


# @app.post("/api/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
# def register(payload: UserCreate, session: Session = Depends(get_session)) -> User:
#     existing = session.exec(select(User).where(User.email == payload.email)).first()
#     if existing:
#         raise HTTPException(status_code=400, detail="Email already registered")
#     user = User(email=payload.email, hashed_password=hash_password(payload.password))
#     session.add(user)
#     session.commit()
#     session.refresh(user)
#     return user


# @app.post("/api/auth/login", response_model=Token)
# def login(
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     session: Session = Depends(get_session),
# ) -> Token:
#     user = authenticate_user(session, form_data.username, form_data.password)
#     if not user:
#         raise HTTPException(status_code=401, detail="Incorrect email or password")
#     return Token(access_token=create_access_token(user.email))


# @app.get("/api/auth/me", response_model=UserRead)
# def me(current_user: User = Depends(get_current_user)) -> User:
#     return current_user


# @app.get("/api/admin/summary", response_model=AdminSummary)
# def admin_summary(
#     _: User = Depends(get_current_admin_user),
#     session: Session = Depends(get_session),
# ) -> AdminSummary:
#     users = session.exec(select(User)).all()
#     datasets = session.exec(select(Dataset)).all()
#     dataset_files = session.exec(select(DatasetFile)).all()
#     return AdminSummary(
#         user_count=len(users),
#         dataset_count=len(datasets),
#         dataset_file_count=len(dataset_files),
#     )


# @app.get("/api/admin/users", response_model=list[AdminUserRead])
# def admin_list_users(
#     _: User = Depends(get_current_admin_user),
#     session: Session = Depends(get_session),
# ) -> list[User]:
#     return list(session.exec(select(User).order_by(User.created_at.desc())))


# @app.get("/api/admin/datasets", response_model=list[AdminDatasetRead])
# def admin_list_datasets(
#     _: User = Depends(get_current_admin_user),
#     session: Session = Depends(get_session),
# ) -> list[AdminDatasetRead]:
#     datasets = session.exec(select(Dataset).order_by(Dataset.created_at.desc())).all()
#     result: list[AdminDatasetRead] = []
#     for dataset in datasets:
#         files = list(
#             session.exec(
#                 select(DatasetFile).where(DatasetFile.dataset_id == dataset.id)
#             )
#         )
#         result.append(
#             AdminDatasetRead(
#                 id=dataset.id,
#                 name=dataset.name,
#                 owner_id=dataset.owner_id,
#                 created_at=dataset.created_at,
#                 file_count=len(files),
#                 total_size_bytes=sum(file.size_bytes for file in files),
#             )
#         )
#     return result


# @app.patch("/api/admin/users/{user_id}/block", response_model=AdminUserRead)
# def admin_block_user(
#     user_id: UUID,
#     current_admin: User = Depends(get_current_admin_user),
#     session: Session = Depends(get_session),
# ) -> User:
#     target_user = get_admin_target_user(user_id, current_admin, session)
#     target_user.is_active = False
#     session.add(target_user)
#     session.commit()
#     session.refresh(target_user)
#     return target_user


# @app.patch("/api/admin/users/{user_id}/unblock", response_model=AdminUserRead)
# def admin_unblock_user(
#     user_id: UUID,
#     current_admin: User = Depends(get_current_admin_user),
#     session: Session = Depends(get_session),
# ) -> User:
#     target_user = get_admin_target_user(user_id, current_admin, session)
#     target_user.is_active = True
#     session.add(target_user)
#     session.commit()
#     session.refresh(target_user)
#     return target_user


# @app.delete("/api/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
# def admin_delete_user(
#     user_id: UUID,
#     current_admin: User = Depends(get_current_admin_user),
#     session: Session = Depends(get_session),
# ) -> None:
#     target_user = get_admin_target_user(user_id, current_admin, session)
#     datasets = session.exec(
#         select(Dataset).where(Dataset.owner_id == target_user.id)
#     ).all()
#     for dataset in datasets:
#         dataset_files = session.exec(
#             select(DatasetFile).where(DatasetFile.dataset_id == dataset.id)
#         ).all()
#         for dataset_file in dataset_files:
#             session.delete(dataset_file)
#         session.delete(dataset)
#         dataset_upload_root = (
#             settings.upload_root / str(target_user.id) / str(dataset.id)
#         )
#         shutil.rmtree(dataset_upload_root, ignore_errors=True)
#     form_submissions = session.exec(
#         select(FormSubmission).where(FormSubmission.owner_id == target_user.id)
#     ).all()
#     for form_submission in form_submissions:
#         session.delete(form_submission)
#     session.delete(target_user)
#     session.commit()


# def safe_relative_path(filename: str) -> Path:
#     """Allow browser directory uploads while blocking ../ path traversal."""
#     posix_path = PurePosixPath(filename.replace("\\", "/"))
#     parts = [part for part in posix_path.parts if part not in ("", ".")]
#     if not parts or any(part == ".." for part in parts):
#         raise HTTPException(status_code=400, detail=f"Unsafe filename: {filename}")
#     return Path(*parts)


# def dataset_to_read(dataset: Dataset, files: list[DatasetFile]) -> DatasetRead:
#     return DatasetRead(
#         id=dataset.id,
#         name=dataset.name,
#         created_at=dataset.created_at,
#         file_count=len(files),
#         total_size_bytes=sum(file.size_bytes for file in files),
#         files=[
#             DatasetFileRead(
#                 id=file.id,
#                 relative_path=file.relative_path,
#                 size_bytes=file.size_bytes,
#                 created_at=file.created_at,
#             )
#             for file in files
#         ],
#     )


# @app.post("/api/datasets", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
# async def create_dataset(
#     name: str = Form(...),
#     files: list[UploadFile] = File(...),
#     current_user: User = Depends(get_current_user),
#     session: Session = Depends(get_session),
# ) -> DatasetRead:
#     dataset_name = name.strip()
#     if not dataset_name:
#         raise HTTPException(status_code=400, detail="Dataset name is required")
#     if not files:
#         raise HTTPException(status_code=400, detail="At least one file is required")
#     existing = session.exec(
#         select(Dataset).where(
#             Dataset.owner_id == current_user.id,
#             Dataset.name == dataset_name,
#         )
#     ).first()
#     if existing:
#         raise HTTPException(status_code=400, detail="A dataset with this name already exists")
#     dataset = Dataset(owner_id=current_user.id, name=dataset_name)
#     session.add(dataset)
#     dataset_upload_root = settings.upload_root / str(current_user.id) / str(dataset.id)
#     dataset_upload_root.mkdir(parents=True, exist_ok=False)
#     dataset_files: list[DatasetFile] = []
#     for upload in files:
#         relative_path = safe_relative_path(upload.filename or "uploaded_file")
#         target_path = dataset_upload_root / relative_path
#         target_path.parent.mkdir(parents=True, exist_ok=True)
#         size_bytes = 0
#         with target_path.open("wb") as out_file:
#             while chunk := await upload.read(1024 * 1024):
#                 size_bytes += len(chunk)
#                 out_file.write(chunk)
#         dataset_file = DatasetFile(
#             dataset_id=dataset.id,
#             relative_path=relative_path.as_posix(),
#             size_bytes=size_bytes,
#         )
#         session.add(dataset_file)
#         dataset_files.append(dataset_file)
#     session.commit()
#     session.refresh(dataset)
#     for dataset_file in dataset_files:
#         session.refresh(dataset_file)
#     return dataset_to_read(dataset, dataset_files)


# @app.get("/api/datasets", response_model=list[DatasetRead])
# def list_datasets(
#     current_user: User = Depends(get_current_user),
#     session: Session = Depends(get_session),
# ) -> list[DatasetRead]:
#     datasets = session.exec(
#         select(Dataset)
#         .where(Dataset.owner_id == current_user.id)
#         .order_by(Dataset.created_at.desc())
#     ).all()
#     result: list[DatasetRead] = []
#     for dataset in datasets:
#         files = list(
#             session.exec(
#                 select(DatasetFile)
#                 .where(DatasetFile.dataset_id == dataset.id)
#                 .order_by(DatasetFile.relative_path)
#             )
#         )
#         result.append(dataset_to_read(dataset, files))
#     return result


# @app.get("/api/datasets/{dataset_id}", response_model=DatasetRead)
# def get_dataset(
#     dataset_id: UUID,
#     current_user: User = Depends(get_current_user),
#     session: Session = Depends(get_session),
# ) -> DatasetRead:
#     dataset = session.exec(
#         select(Dataset).where(
#             Dataset.id == dataset_id,
#             Dataset.owner_id == current_user.id,
#         )
#     ).first()
#     if dataset is None:
#         raise HTTPException(status_code=404, detail="Dataset not found")
#     files = list(
#         session.exec(
#             select(DatasetFile)
#             .where(DatasetFile.dataset_id == dataset.id)
#             .order_by(DatasetFile.relative_path)
#         )
#     )
#     return dataset_to_read(dataset, files)


# @app.delete("/api/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_dataset(
#     dataset_id: UUID,
#     current_user: User = Depends(get_current_user),
#     session: Session = Depends(get_session),
# ) -> None:
#     dataset = session.exec(
#         select(Dataset).where(
#             Dataset.id == dataset_id,
#             Dataset.owner_id == current_user.id,
#         )
#     ).first()
#     if dataset is None:
#         raise HTTPException(status_code=404, detail="Dataset not found")
#     dataset_files = session.exec(
#         select(DatasetFile).where(DatasetFile.dataset_id == dataset.id)
#     ).all()
#     for dataset_file in dataset_files:
#         session.delete(dataset_file)
#     session.delete(dataset)
#     session.commit()
#     dataset_upload_root = settings.upload_root / str(current_user.id) / str(dataset.id)
#     shutil.rmtree(dataset_upload_root, ignore_errors=True)


# @app.post("/api/forms", response_model=FormSubmissionRead, status_code=status.HTTP_201_CREATED)
# def create_form_submission(
#     payload: FormSubmissionCreate,
#     current_user: User = Depends(get_current_user),
#     session: Session = Depends(get_session),
# ) -> FormSubmission:
#     submission = FormSubmission(owner_id=current_user.id, **payload.model_dump())
#     session.add(submission)
#     session.commit()
#     session.refresh(submission)
#     return submission


# @app.get("/api/forms", response_model=list[FormSubmissionRead])
# def list_form_submissions(
#     current_user: User = Depends(get_current_user),
#     session: Session = Depends(get_session),
# ) -> list[FormSubmission]:
#     return list(
#         session.exec(
#             select(FormSubmission)
#             .where(FormSubmission.owner_id == current_user.id)
#             .order_by(FormSubmission.created_at.desc())
#         )
#     )


# @app.post("/api/tasks/demo", status_code=status.HTTP_202_ACCEPTED)
# def start_demo_task(
#     seconds: int = Query(default=5, ge=1, le=300),
#     _: User = Depends(get_current_user),
# ) -> dict[str, str]:
#     """Start a small Celery task to verify the background worker setup."""
#     task = demo_background_task.delay(seconds)
#     return {"task_id": task.id, "status": "queued"}


# @app.get("/api/tasks/{task_id}")
# def get_task_status(
#     task_id: str,
#     _: User = Depends(get_current_user),
# ) -> dict[str, object]:
#     """Return Celery state/result metadata for a queued background task."""
#     result = AsyncResult(task_id, app=celery_app)
#     response: dict[str, object] = {"task_id": task_id, "state": result.state}
#     if result.state == "PENDING":
#         response["message"] = "Task is pending or unknown"
#     elif result.state == "FAILURE":
#         response["message"] = str(result.info)
#     elif isinstance(result.info, dict):
#         response.update(result.info)
#     elif result.ready():
#         response["result"] = result.result
#     return response