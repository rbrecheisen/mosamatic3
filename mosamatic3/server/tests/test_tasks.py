from typing import Any

from fastapi.testclient import TestClient


def test_list_tasks_and_get_demo_schema(
  client: TestClient,
  auth_headers: dict[str, str],
) -> None:
  list_response = client.get("/api/tasks", headers=auth_headers)
  assert list_response.status_code == 200
  task_ids = {task["id"] for task in list_response.json()}
  assert {"demo", "rescaledicomimages"}.issubset(task_ids)

  schema_response = client.get("/api/tasks/demo/schema", headers=auth_headers)
  assert schema_response.status_code == 200
  schema = schema_response.json()
  assert schema["id"] == "demo"
  assert "text_value" in schema["schema"]["properties"]
  assert "dataset_id" in schema["schema"]["properties"]


def test_save_read_and_run_demo_task_parameters(
  client: TestClient,
  auth_headers: dict[str, str],
  make_dataset,
  monkeypatch,
) -> None:
  dataset = make_dataset()
  payload = {
    "task_key": "demo",
    "parameters": {
      "text_value": "Hello test",
      "integer_value": 0,
      "float_value": 1.5,
      "slider_value": 50,
      "processing_mode": "balanced",
      "enable_debug_output": True,
      "dataset_id": dataset["id"],
      "dataset_ids": [dataset["id"]],
    },
  }

  save_response = client.post(
    "/api/tasks/demo/parameters",
    headers=auth_headers,
    json=payload,
  )
  assert save_response.status_code == 200, save_response.text
  saved = save_response.json()
  assert saved["exists"] is True
  assert saved["is_valid"] is True
  assert saved["parameters"]["text_value"] == "Hello test"

  read_response = client.get("/api/tasks/demo/parameters", headers=auth_headers)
  assert read_response.status_code == 200
  assert read_response.json()["parameters"]["dataset_id"] == dataset["id"]

  sent_tasks: list[dict[str, Any]] = []

  class FakeCeleryResult:
    id = "fake-task-id"

  def fake_send_task(name: str, args: list[Any]):
    sent_tasks.append({"name": name, "args": args})
    return FakeCeleryResult()

  monkeypatch.setattr("app.services.taskservice.celery_app.send_task", fake_send_task)

  run_response = client.post("/api/tasks/demo/run", headers=auth_headers)

  assert run_response.status_code == 202
  assert run_response.json() == {"task_id": "fake-task-id", "status": "queued"}
  assert sent_tasks[0]["name"] == "app.tasks.demo.celerytasks.run_demotask"
  assert sent_tasks[0]["args"][0]["dataset_id"] == dataset["id"]


def test_run_task_requires_saved_valid_parameters(
  client: TestClient,
  auth_headers: dict[str, str],
) -> None:
  response = client.post("/api/tasks/demo/run", headers=auth_headers)

  assert response.status_code == 400
  assert response.json()["detail"] == "Valid task parameters must be submitted before running this task."


def test_saving_parameters_rejects_unknown_dataset(
  client: TestClient,
  auth_headers: dict[str, str],
) -> None:
  missing_dataset_id = "00000000-0000-0000-0000-000000000001"
  response = client.post(
    "/api/tasks/rescaledicomimages/parameters",
    headers=auth_headers,
    json={
      "task_key": "rescaledicomimages",
      "parameters": {
        "dataset_id": missing_dataset_id,
        "target_size": 512,
        "overwrite_existing": False,
      },
    },
  )

  assert response.status_code == 404
  assert response.json()["detail"] == f"Dataset not found: {missing_dataset_id}"


def test_saving_parameters_rejects_task_key_mismatch(
  client: TestClient,
  auth_headers: dict[str, str],
) -> None:
  response = client.post(
    "/api/tasks/demo/parameters",
    headers=auth_headers,
    json={"task_key": "rescaledicomimages", "parameters": {}},
  )

  assert response.status_code == 400
  assert response.json()["detail"] == "Task key in URL and request body do not match."
