from collections.abc import Generator
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.config.config import settings
from app.data.database import get_session
from app.main import app


@pytest.fixture(name="test_engine")
def test_engine_fixture():
  engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  SQLModel.metadata.create_all(engine)
  try:
    yield engine
  finally:
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(test_engine) -> Generator[Session, None, None]:
  with Session(test_engine) as session:
    yield session


@pytest.fixture(name="client")
def client_fixture(test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
  settings.upload_root = tmp_path / "uploads"
  settings.upload_root.mkdir(parents=True, exist_ok=True)

  monkeypatch.setattr("app.services.authservice.hash_password", lambda password: f"test-hash:{password}")
  monkeypatch.setattr(
    "app.services.authservice.verify_password",
    lambda plain_password, hashed_password: hashed_password == f"test-hash:{plain_password}",
  )

  def override_get_session() -> Generator[Session, None, None]:
    with Session(test_engine) as session:
      yield session

  app.dependency_overrides[get_session] = override_get_session
  client = TestClient(app)
  try:
    yield client
  finally:
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
  email = "ralph@example.com"
  password = "secret123"
  client.post(
    "/api/auth/register",
    json={"email": email, "password": password},
  )
  response = client.post(
    "/api/auth/login",
    data={"username": email, "password": password},
  )
  token = response.json()["access_token"]
  return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_dataset(client: TestClient, auth_headers: dict[str, str]):
  def _make_dataset(name: str = "Input dataset") -> dict[str, Any]:
    response = client.post(
      "/api/datasets",
      headers=auth_headers,
      data={"name": name},
      files=[
        ("files", ("image1.dcm", b"dicom-1", "application/dicom")),
        ("files", ("nested/image2.dcm", b"dicom-2", "application/dicom")),
      ],
    )
    assert response.status_code == 201, response.text
    return response.json()

  return _make_dataset
