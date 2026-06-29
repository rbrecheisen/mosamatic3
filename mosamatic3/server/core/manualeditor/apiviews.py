from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .services import (
    get_image_payload,
    get_manual_correction_output_dataset,
    get_manual_correction_output_datasets,
    get_manual_editor_cases,
    get_manual_editor_datasets_for_user,
    get_owned_dataset,
    get_owned_dataset_file,
    get_segmentation_payload,
    save_corrected_segmentation,
)


@api_view(["GET"])
def manual_editor_datasets(request):
    datasets = get_manual_editor_datasets_for_user(request.user)

    return Response(
        [
            {
                "id": str(dataset.id),
                "name": dataset.name,
                "kind": dataset.kind,
                "status": dataset.status,
                "source_task_key": dataset.source_task_key,
                "source_task_id": dataset.source_task_id,
                "file_count": dataset.file_count,
                "created_at": dataset.created_at,
            }
            for dataset in datasets
        ]
    )


@api_view(["GET"])
def manual_editor_correction_datasets(request, dataset_id):
    source_dataset = get_owned_dataset(request.user, dataset_id)
    output_datasets = get_manual_correction_output_datasets(
        source_dataset=source_dataset,
        user=request.user,
    )

    return Response(
        [
            {
                "id": str(dataset.id),
                "name": dataset.name,
                "kind": dataset.kind,
                "status": dataset.status,
                "source_task_key": dataset.source_task_key,
                "source_dataset_id": str(dataset.source_dataset_id),
                "file_count": dataset.file_count,
                "created_at": dataset.created_at,
            }
            for dataset in output_datasets
        ]
    )


@api_view(["GET"])
def manual_editor_cases(request, dataset_id):
    source_dataset = get_owned_dataset(request.user, dataset_id)

    output_dataset_id = request.query_params.get("output_dataset_id") or None

    correction_dataset = get_manual_correction_output_dataset(
        source_dataset=source_dataset,
        user=request.user,
        output_dataset_id=output_dataset_id,
        create_if_missing=False,
    )

    cases = get_manual_editor_cases(
        source_dataset,
        request.user,
        correction_dataset=correction_dataset,
    )

    return Response(
        [
            {
                "image_file_id": str(case.image_file.id),
                "image_relative_path": case.image_file.relative_path,

                "segmentation_file_id": (
                    str(case.segmentation_file.id)
                    if case.segmentation_file is not None
                    else None
                ),
                "segmentation_relative_path": (
                    case.segmentation_file.relative_path
                    if case.segmentation_file is not None
                    else None
                ),

                "correction_image_file_id": (
                    str(case.correction_image_file.id)
                    if case.correction_image_file is not None
                    else None
                ),
                "correction_image_relative_path": (
                    case.correction_image_file.relative_path
                    if case.correction_image_file is not None
                    else None
                ),

                "correction_segmentation_file_id": (
                    str(case.correction_segmentation_file.id)
                    if case.correction_segmentation_file is not None
                    else None
                ),
                "correction_segmentation_relative_path": (
                    case.correction_segmentation_file.relative_path
                    if case.correction_segmentation_file is not None
                    else None
                ),

                "has_segmentation": case.segmentation_file is not None,
                "has_correction": case.correction_segmentation_file is not None,
            }
            for case in cases
        ]
    )


@api_view(["GET"])
def manual_editor_image(request, file_id):
    dataset_file = get_owned_dataset_file(request.user, file_id)
    return Response(get_image_payload(dataset_file, request.user))


@api_view(["GET"])
def manual_editor_segmentation(request, file_id):
    dataset_file = get_owned_dataset_file(request.user, file_id)
    return Response(get_segmentation_payload(dataset_file, request.user))


@api_view(["POST"])
def manual_editor_save_correction(request, file_id):
    image_file = get_owned_dataset_file(request.user, file_id)

    source_dataset_id = request.data.get("source_dataset_id")
    output_dataset_id = request.data.get("output_dataset_id") or None
    rows = request.data.get("rows")
    columns = request.data.get("columns")
    mask_base64 = request.data.get("mask_base64")

    if not source_dataset_id:
        raise ValidationError("source_dataset_id is required")

    if rows is None or columns is None or not mask_base64:
        raise ValidationError("rows, columns and mask_base64 are required")

    source_dataset = get_owned_dataset(request.user, source_dataset_id)

    if image_file.dataset_id != source_dataset.id:
        raise ValidationError("The image file does not belong to the selected source dataset")

    result = save_corrected_segmentation(
        source_dataset=source_dataset,
        image_file=image_file,
        user=request.user,
        rows=int(rows),
        columns=int(columns),
        mask_base64=mask_base64,
        output_dataset_id=output_dataset_id,
    )

    return Response(result, status=status.HTTP_201_CREATED)