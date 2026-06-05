from zipfile import ZipFile
from io import BytesIO

from fastapi.testclient import TestClient


def test_dataset_upload_list_get_download_and_delete(
  client: TestClient,
  auth_headers: dict[str, str],
) -> None:
  upload_response = client.post(
    "/api/datasets",
    headers=auth_headers,
    data={"name": "CT files"},
    files=[
      ("files", ("slice1.dcm", b"slice-1", "application/dicom")),
      ("files", ("series/slice2.dcm", b"slice-2", "application/dicom")),
    ],
  )
  assert upload_response.status_code == 201, upload_response.text
  dataset = upload_response.json()
  assert dataset["name"] == "CT files"
  assert dataset["kind"] == "input"
  assert dataset["file_count"] == 2
  assert dataset["total_size_bytes"] == len(b"slice-1") + len(b"slice-2")
  assert [file["relative_path"] for file in dataset["files"]] == [
    "slice1.dcm",
    "series/slice2.dcm",
  ]

  list_response = client.get("/api/datasets", headers=auth_headers)
  assert list_response.status_code == 200
  assert [item["id"] for item in list_response.json()] == [dataset["id"]]

  get_response = client.get(f"/api/datasets/{dataset['id']}", headers=auth_headers)
  assert get_response.status_code == 200
  assert get_response.json()["id"] == dataset["id"]

  download_response = client.get(
    f"/api/datasets/{dataset['id']}/download",
    headers=auth_headers,
  )
  assert download_response.status_code == 200
  assert download_response.headers["content-type"] == "application/zip"
  with ZipFile(BytesIO(download_response.content)) as zip_file:
    assert sorted(zip_file.namelist()) == ["series/slice2.dcm", "slice1.dcm"]
    assert zip_file.read("slice1.dcm") == b"slice-1"

  delete_response = client.delete(f"/api/datasets/{dataset['id']}", headers=auth_headers)
  assert delete_response.status_code == 204
  assert client.get(f"/api/datasets/{dataset['id']}", headers=auth_headers).status_code == 404


def test_dataset_upload_rejects_unsafe_filename(
  client: TestClient,
  auth_headers: dict[str, str],
) -> None:
  response = client.post(
    "/api/datasets",
    headers=auth_headers,
    data={"name": "Bad files"},
    files=[("files", ("../evil.dcm", b"bad", "application/dicom"))],
  )

  assert response.status_code == 400
  assert "Unsafe filename" in response.json()["detail"]


def test_user_cannot_access_another_users_dataset(client: TestClient) -> None:
  client.post(
    "/api/auth/register",
    json={"email": "owner@example.com", "password": "secret123"},
  )
  owner_login = client.post(
    "/api/auth/login",
    data={"username": "owner@example.com", "password": "secret123"},
  )
  owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
  dataset_response = client.post(
    "/api/datasets",
    headers=owner_headers,
    data={"name": "Private dataset"},
    files=[("files", ("slice.dcm", b"slice", "application/dicom"))],
  )
  dataset_id = dataset_response.json()["id"]

  client.post(
    "/api/auth/register",
    json={"email": "other@example.com", "password": "secret123"},
  )
  other_login = client.post(
    "/api/auth/login",
    data={"username": "other@example.com", "password": "secret123"},
  )
  other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

  response = client.get(f"/api/datasets/{dataset_id}", headers=other_headers)

  assert response.status_code == 404
