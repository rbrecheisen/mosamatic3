import io
import json
import os
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import redirect, render

from ..models import Dataset


@login_required
def admin_panel_page(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access required')
        return redirect('home')

    return render(
        request,
        'adminpanel/admin_panel.html',
        {
            'users': User.objects.order_by('username'),
            'datasets': Dataset.objects.all().prefetch_related('files'),
        },
    )


@login_required
def download_support_bundle(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access required')
        return redirect('home')

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    zip_filename = f'mosamatic3-support-bundle-{timestamp}.zip'

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        _write_system_info(zip_file)
        _write_log_files(zip_file)

    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    return response


def _write_system_info(zip_file: zipfile.ZipFile) -> None:
    system_info = {
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'app': {
            'name': 'Mosamatic3',
            'debug': bool(settings.DEBUG),
            'allowed_hosts': list(settings.ALLOWED_HOSTS),
        },
        'python': {
            'version': sys.version,
            'executable': sys.executable,
        },
        'platform': {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
        },
        'django': {
            'database_engine': settings.DATABASES['default']['ENGINE'],
            'static_root': str(settings.STATIC_ROOT),
            'upload_root': str(settings.UPLOAD_ROOT),
            'log_dir': str(getattr(settings, 'LOG_DIR', '')),
        },
        'celery': {
            'broker_configured': bool(getattr(settings, 'CELERY_BROKER_URL', '')),
            'result_backend_configured': bool(getattr(settings, 'CELERY_RESULT_BACKEND', '')),
        },
        'environment': {
            'docker_container_role': os.getenv('CELERY_WORKER_NAME', 'web'),
            'log_level': os.getenv('LOG_LEVEL', ''),
            'gunicorn_workers': os.getenv('GUNICORN_WORKERS', ''),
            'gunicorn_timeout': os.getenv('GUNICORN_TIMEOUT', ''),
        },
        'counts': {
            'users': User.objects.count(),
            'datasets': Dataset.objects.count(),
        },
    }

    zip_file.writestr(
        'system-info.json',
        json.dumps(system_info, indent=2, sort_keys=True),
    )


def _write_log_files(zip_file: zipfile.ZipFile) -> None:
    log_dir = Path(getattr(settings, 'LOG_DIR', settings.BASE_DIR / 'data' / 'logs'))

    if not log_dir.exists():
        zip_file.writestr(
            'logs/README.txt',
            f'No log directory found at: {log_dir}',
        )
        return

    log_files = sorted(
        [
            path
            for path in log_dir.iterdir()
            if path.is_file()
            and (
                path.name.endswith('.log')
                or '.log.' in path.name
                or path.name.endswith('.txt')
            )
        ],
        key=lambda p: p.name,
    )

    if not log_files:
        zip_file.writestr(
            'logs/README.txt',
            f'No log files found at: {log_dir}',
        )
        return

    for log_file in log_files:
        zip_file.write(
            log_file,
            arcname=f'logs/{log_file.name}',
        )