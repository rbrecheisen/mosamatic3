from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config.config import settings
from .mainstartup import on_startup
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
  expose_headers=["Content-Disposition"], # For ZIP downloads
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(forms.router, prefix="/api/forms", tags=["forms"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])