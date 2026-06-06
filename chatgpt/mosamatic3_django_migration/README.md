# Mosamatic3 Django migration

This ZIP is a Django REST Framework + server-rendered HTML migration of the uploaded FastAPI + Vite/React app.

## What changed

- FastAPI was replaced by Django + Django REST Framework.
- The `/api/...` endpoints keep the same general shape as the original app.
- The React/Vite UI was replaced by normal Django templates and small vanilla JavaScript snippets.
- Celery/Redis task execution is preserved.
- Datasets, dataset files, task parameters, task runs, and form submissions are Django models.
- The original `demo` and `rescaledicomimages` tasks are migrated; `sliceselect` is included as a registered placeholder only if you enable it in the registry.

## Local setup

```bash
cd mosamatic3_django
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
mkdir -p data
printf "admin123" > data/admin_password.txt
python manage.py migrate
python manage.py ensure_admin
python manage.py runserver
```

Start Redis separately, then run the worker:

```bash
celery -A config.celery_app worker --loglevel=info --pool=solo
```

Open `http://localhost:8000/`. The default admin login is controlled by `ADMIN_USERNAME` and `ADMIN_PASSWORD_FILE`.

## Docker

```bash
docker compose up --build
```

The app is served directly by Django on port `8000`; there is no Vite/NGINX frontend container anymore.

## Main URLs

- HTML UI: `/`, `/data/`, `/analysis/`, `/analysis/<task_key>/`, `/admin-panel/`
- API: `/api/health`, `/api/auth/login`, `/api/auth/register`, `/api/auth/me`, `/api/datasets`, `/api/tasks`, `/api/admin/...`

## Notes

This is a generated migration scaffold, not a hand-verified production rewrite. The API surface and task structure are preserved as closely as practical, but you should run through your normal app flows and tighten edge cases before deploying.
