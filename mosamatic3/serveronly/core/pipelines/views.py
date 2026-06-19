from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.models import Dataset, PipelineRun
from .configloader import list_pipeline_configs


@login_required
def pipelines(request):
    input_datasets = Dataset.objects.filter(
        owner=request.user,
        kind=Dataset.KIND_INPUT,
    ).order_by("-created_at")

    pipeline_runs = PipelineRun.objects.filter(
        owner=request.user,
    ).order_by("-created_at")[:25]

    pipeline_configs = list_pipeline_configs()

    return render(
        request,
        "pipelines/pipelines.html",
        {
            "pipeline_configs": pipeline_configs,
            "input_datasets": input_datasets,
            "pipeline_runs": pipeline_runs,
        },
    )