from typing import Any
from ...app import celery_app
from app.processing.tasks.demo.demo import run_task


@celery_app.task(bind=True, name="app.processing.tasks.demo.demotask")
def demotask(
    self,
    seconds: int = 5,
    single_dataset_id: str | None = None,
    text_value: str = "",
    checkbox_value: bool = False,
    slider_value: float = 50,
    dataset_ids: list[str] | None = None,
) -> dict[str, Any]:
    selected_dataset_ids = dataset_ids or []
    total_steps = max(1, int(seconds))
    submitted_parameters = {
        "seconds": total_steps,
        "single_dataset_id": single_dataset_id,
        "text_value": text_value,
        "checkbox_value": checkbox_value,
        "slider_value": slider_value,
        "dataset_ids": selected_dataset_ids,
    }

    print("Demo task parameters:", submitted_parameters)
    if single_dataset_id:
        print(f"Single dataset selected: {single_dataset_id}")
    for dataset_id in selected_dataset_ids:
        print(f"Dataset from selected list: {dataset_id}")

    for step in range(total_steps):
        self.update_state(
            state="PROGRESS",
            meta={
                "current": step + 1,
                "total": total_steps,
                "message": f"Processing step {step + 1} of {total_steps}",
                "parameters": submitted_parameters,
            },
        )
        run_task()
    return {
        "current": total_steps,
        "total": total_steps,
        "message": "Task completed",
        "parameters": submitted_parameters,
    }
