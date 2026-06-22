import json

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render

from core.models import Dataset, PipelineRun
from core.tasking.registry import TASKS

from .configloader import list_pipeline_configs, load_pipeline_config


@login_required
def pipelines(request):
    pipeline_runs = PipelineRun.objects.filter(
        owner=request.user,
    ).order_by("-created_at")[:25]

    pipeline_configs = list_pipeline_configs()

    return render(
        request,
        "pipelines/pipelines.html",
        {
            "pipeline_configs": pipeline_configs,
            "pipeline_runs": pipeline_runs,
        },
    )


@login_required
def pipeline_detail(request, config_key):
    try:
        config = load_pipeline_config(config_key)
    except FileNotFoundError:
        messages.error(request, f"Unknown pipeline config: {config_key}")
        return redirect("pipelines")

    datasets = Dataset.objects.filter(
        owner=request.user,
    ).order_by("kind", "name")

    input_datasets = Dataset.objects.filter(
        owner=request.user,
        kind=Dataset.KIND_INPUT,
    ).order_by("-created_at")

    form_steps = build_pipeline_form_steps(config)

    return render(
        request,
        "pipelines/pipeline_detail.html",
        {
            "config_key": config_key,
            "config": config,
            "form_steps_json": json.dumps(form_steps),
            "datasets": datasets,
            "input_datasets": input_datasets,
        },
    )


def build_pipeline_form_steps(config: dict) -> list[dict]:
    """
    Build UI metadata from:
    - pipeline config step parameters
    - task parameter schemas

    Only parameters explicitly present in the pipeline JSON are exposed.
    The chained input dataset parameter is hidden, because the pipeline runner injects it.
    """

    form_steps = []

    for step in config.get("steps", []):
        task_key = step["task_key"]
        task = TASKS[task_key]

        schema = task.parameter_schema.model_json_schema()
        schema_properties = schema.get("properties", {})
        required_fields = set(schema.get("required", []))

        input_parameter = step.get("input_parameter")
        configured_parameters = step.get("parameters") or {}

        fields = []

        for parameter_name, configured_value in configured_parameters.items():
            if parameter_name == input_parameter:
                continue

            field_schema = dict(schema_properties.get(parameter_name, {}))
            field_schema["name"] = parameter_name
            field_schema["value"] = configured_value
            field_schema["required"] = parameter_name in required_fields

            fields.append(field_schema)

        form_steps.append(
            {
                "id": step["id"],
                "task_key": task_key,
                "task_name": task.name,
                "description": task.description,
                "input_dataset": step.get("input_dataset"),
                "fields": fields,
            }
        )

    return form_steps