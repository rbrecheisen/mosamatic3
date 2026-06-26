conda activate mosamatic3

$env:PYTHONPATH = "D:\SoftwareDevelopment\GitHub\mosamatic3\mosamatic3\server;$env:PYTHONPATH"

# Start Redis only, not the Docker worker
& ".\run-dockerbackendservices.ps1"

python manage.py makemigrations --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py ensure_admin

# Start Celery pipeline worker in a separate PowerShell window
Start-Process powershell.exe -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "conda activate mosamatic3; cd '$PWD'; `$env:PYTHONPATH='D:\SoftwareDevelopment\GitHub\mosamatic3\mosamatic3\server;' + `$env:PYTHONPATH; python -m celery -A config.celery_app worker --loglevel=info --pool=solo -Q pipeline -n pipeline@%h"
)

# Start Celery task worker in a separate PowerShell window
Start-Process powershell.exe -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "conda activate mosamatic3; cd '$PWD'; `$env:PYTHONPATH='D:\SoftwareDevelopment\GitHub\mosamatic3\mosamatic3\server;' + `$env:PYTHONPATH; python -m celery -A config.celery_app worker --loglevel=info --pool=solo -Q tasks -n tasks@%h"
)

# Start Django in this window
python manage.py runserver