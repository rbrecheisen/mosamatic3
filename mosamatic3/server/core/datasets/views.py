import json
import mimetypes
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from ..models import Dataset, DatasetFile
from .services import get_dataset_file_path


VIEWABLE_IMAGE_EXTENSIONS = {
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.webp',
    '.bmp',
}

VIEWABLE_TEXT_EXTENSIONS = {
    '.txt',
    '.json',
    '.csv',
    '.md',
    '.log',
    '.xml',
    '.html',
    '.htm',
}

MAX_TEXT_PREVIEW_BYTES = 2 * 1024 * 1024


def _file_extension(relative_path: str) -> str:
    return Path(relative_path).suffix.lower()


def _file_preview_type(relative_path: str) -> str | None:
    extension = _file_extension(relative_path)

    if extension in VIEWABLE_IMAGE_EXTENSIONS:
        return 'image'

    if extension in VIEWABLE_TEXT_EXTENSIONS:
        return 'text'

    return None


def _build_file_rows(dataset: Dataset):
    rows = []

    for dataset_file in dataset.files.all():
        preview_type = _file_preview_type(dataset_file.relative_path)
        rows.append(
            {
                'file': dataset_file,
                'is_viewable': preview_type is not None,
                'preview_type': preview_type,
            }
        )

    return rows


@login_required
def data_page(request):
    datasets = (
        Dataset.objects
        .filter(owner=request.user)
        .prefetch_related('files')
        .order_by('-created_at')
    )
    input_datasets = [d for d in datasets if d.kind != 'output']
    output_datasets = [d for d in datasets if d.kind == 'output']

    return render(
        request,
        'datasets/data.html',
        {
            'input_datasets': input_datasets,
            'output_datasets': output_datasets,
            'output_empty_message': 'No output results yet. Run a task to generate output datasets.',
        },
    )


@login_required
def dataset_detail_page(request, dataset_id, file_id=None):
    dataset = get_object_or_404(
        Dataset.objects.prefetch_related('files'),
        id=dataset_id,
        owner=request.user,
    )

    selected_file = None
    selected_preview_type = None
    selected_text_content = None
    selected_text_truncated = False

    if file_id is not None:
        selected_file = get_object_or_404(
            DatasetFile,
            id=file_id,
            dataset=dataset,
        )

        selected_preview_type = _file_preview_type(selected_file.relative_path)

        if selected_preview_type is None:
            raise Http404('This file type cannot be previewed in the browser.')

        if selected_preview_type == 'text':
            file_path = get_dataset_file_path(
                request.user.id,
                dataset.id,
                selected_file.relative_path,
            )

            raw = file_path.read_bytes()
            if len(raw) > MAX_TEXT_PREVIEW_BYTES:
                raw = raw[:MAX_TEXT_PREVIEW_BYTES]
                selected_text_truncated = True

            text = raw.decode('utf-8', errors='replace')

            if _file_extension(selected_file.relative_path) == '.json':
                try:
                    parsed = json.loads(text)
                    text = json.dumps(parsed, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    pass

            selected_text_content = text

    return render(
        request,
        'datasets/dataset_detail.html',
        {
            'dataset': dataset,
            'file_rows': _build_file_rows(dataset),
            'selected_file': selected_file,
            'selected_preview_type': selected_preview_type,
            'selected_text_content': selected_text_content,
            'selected_text_truncated': selected_text_truncated,
        },
    )


@login_required
def dataset_file_raw(request, dataset_id, file_id):
    dataset = get_object_or_404(
        Dataset,
        id=dataset_id,
        owner=request.user,
    )

    dataset_file = get_object_or_404(
        DatasetFile,
        id=file_id,
        dataset=dataset,
    )

    if _file_preview_type(dataset_file.relative_path) != 'image':
        raise Http404('Only image files can be served as raw browser previews.')

    file_path = get_dataset_file_path(
        request.user.id,
        dataset.id,
        dataset_file.relative_path,
    )

    content_type, _ = mimetypes.guess_type(dataset_file.relative_path)

    return FileResponse(
        file_path.open('rb'),
        content_type=content_type or 'application/octet-stream',
    )