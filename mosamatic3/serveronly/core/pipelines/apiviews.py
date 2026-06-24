from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .service import (
    cancel_pipeline_run,
    create_pipeline_run,
    get_available_pipelines,
    get_pipeline_status,
    delete_pipeline_run,
    delete_all_pipeline_runs,
)


@api_view(["GET"])
def pipeline_list(request):
    return Response(get_available_pipelines())


@api_view(["POST"])
def pipeline_run(request):
    pipeline = create_pipeline_run(
        user=request.user,
        config_key=request.data.get("config_key"),
        initial_dataset_id=request.data.get("initial_dataset_id"),
        overrides=request.data.get("overrides") or {},
    )

    return Response(
        {
            "pipeline_run_id": str(pipeline.id),
            "status": pipeline.status,
            "celery_task_id": pipeline.celery_task_id,
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["GET"])
def pipeline_status(request, pipeline_run_id):
    return Response(get_pipeline_status(pipeline_run_id, request.user))


@api_view(["POST"])
def pipeline_cancel(request, pipeline_run_id):
    pipeline = cancel_pipeline_run(pipeline_run_id, request.user)

    return Response(
        {
            "pipeline_run_id": str(pipeline.id),
            "status": pipeline.status,
            "message": "Cancel requested",
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["POST"])
def pipeline_delete(request, pipeline_run_id):
    delete_pipeline_run(pipeline_run_id, request.user)

    return Response(
        {
            "pipeline_run_id": str(pipeline_run_id),
            "message": "Pipeline run deleted",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
def pipeline_delete_all(request):
    deleted_count = delete_all_pipeline_runs(request.user)

    return Response(
        {
            "message": "Pipeline runs deleted",
            "deleted_count": deleted_count,
        },
        status=status.HTTP_200_OK,
    )