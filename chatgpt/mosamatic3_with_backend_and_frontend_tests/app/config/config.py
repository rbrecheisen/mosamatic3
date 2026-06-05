from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# app/config/config.py -> app/config -> app -> project/server root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
  app_name: str = "mosamatic3"
  secret_key: str = "change-me-in-production"
  algorithm: str = "HS256"
  access_token_expire_minutes: int = 60 * 24
  database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"
  upload_root: Path = DATA_DIR / "uploads"
  frontend_origin: str = "http://localhost:5173"
  admin_username: str = "admin"
  admin_password_file: Path = DATA_DIR / "admin_password.txt"
  celery_broker_url: str = "redis://localhost:6379/0"
  celery_result_backend: str = "redis://localhost:6379/0"
  model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
  )


settings = Settings()
settings.upload_root.mkdir(parents=True, exist_ok=True)
settings.admin_password_file.parent.mkdir(parents=True, exist_ok=True)

# from pathlib import Path
# from pydantic_settings import BaseSettings, SettingsConfigDict


# class Settings(BaseSettings):
#   app_name: str = "mosamatic3"
#   secret_key: str = "change-me-in-production"
#   algorithm: str = "HS256"
#   access_token_expire_minutes: int = 60 * 24
#   database_url: str = "sqlite:////data/app.db"
#   upload_root: Path = Path("/data/uploads")
#   frontend_origin: str = "http://localhost:5173"
#   admin_username: str = "admin"
#   admin_password_file: Path = Path("/run/secrets/admin_password.txt")
#   celery_broker_url: str = "redis://localhost:6379/0"
#   celery_result_backend: str = "redis://localhost:6379/0"
#   model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# settings = Settings()
# settings.upload_root.mkdir(parents=True, exist_ok=True)