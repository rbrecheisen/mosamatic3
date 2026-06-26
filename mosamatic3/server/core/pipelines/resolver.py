from uuid import UUID


def resolve_dataset_reference(value, context: dict) -> str:
    """
    Resolves strings like:
      $initial_dataset
      $steps.rescale.output_dataset

    Returns dataset ID as string.
    """

    if isinstance(value, UUID):
        return str(value)

    if value == "$initial_dataset":
        return str(context["initial_dataset"])

    if not isinstance(value, str):
        return str(value)

    prefix = "$steps."
    suffix = ".output_dataset"

    if value.startswith(prefix) and value.endswith(suffix):
        step_id = value[len(prefix):-len(suffix)]
        try:
            return str(context["steps"][step_id]["output_dataset"])
        except KeyError as exc:
            raise ValueError(
                f"Pipeline step output not available for reference: {value}"
            ) from exc

    return str(value)


def extract_first_output_dataset_id(task_result: dict) -> str:
    """
    Your existing tasks return:

      {
        "output_datasets": [
          {"id": "...", ...}
        ]
      }

    This extracts the first output dataset ID.
    """

    output_datasets = task_result.get("output_datasets") or []

    if not output_datasets:
        raise ValueError("Task result did not contain output_datasets")

    first = output_datasets[0]

    if "id" not in first:
        raise ValueError("Task result output_datasets[0] did not contain id")

    return str(first["id"])