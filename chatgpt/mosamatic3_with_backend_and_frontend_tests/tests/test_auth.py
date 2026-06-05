from fastapi.testclient import TestClient


def test_register_login_and_get_current_user(client: TestClient) -> None:
  register_response = client.post(
    "/api/auth/register",
    json={"email": "user@example.com", "password": "secret123"},
  )
  assert register_response.status_code == 201
  registered_user = register_response.json()
  assert registered_user["email"] == "user@example.com"
  assert registered_user["is_active"] is True
  assert registered_user["is_admin"] is False
  assert "hashed_password" not in registered_user

  login_response = client.post(
    "/api/auth/login",
    data={"username": "user@example.com", "password": "secret123"},
  )
  assert login_response.status_code == 200
  token = login_response.json()["access_token"]

  me_response = client.get(
    "/api/auth/me",
    headers={"Authorization": f"Bearer {token}"},
  )
  assert me_response.status_code == 200
  assert me_response.json()["email"] == "user@example.com"


def test_register_rejects_duplicate_email(client: TestClient) -> None:
  payload = {"email": "duplicate@example.com", "password": "secret123"}
  assert client.post("/api/auth/register", json=payload).status_code == 201

  response = client.post("/api/auth/register", json=payload)

  assert response.status_code == 400
  assert response.json()["detail"] == "Email already registered"


def test_login_rejects_wrong_password(client: TestClient) -> None:
  client.post(
    "/api/auth/register",
    json={"email": "user@example.com", "password": "secret123"},
  )

  response = client.post(
    "/api/auth/login",
    data={"username": "user@example.com", "password": "wrong"},
  )

  assert response.status_code == 401
