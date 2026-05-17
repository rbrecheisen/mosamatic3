# Celery background jobs

This project now has a Celery setup using Redis as broker and result backend.

## Docker

Make sure `data/admin_password.txt` exists, then run:

```bash
docker compose up --build
```

This starts:

- `server`: FastAPI app on http://localhost:8000
- `worker`: Celery worker
- `redis`: Redis broker/result backend
- `ui`: React UI on http://localhost:5173

## Without Docker

Install the backend dependencies, start Redis locally, then run FastAPI and Celery in two separate terminals:

```bash
pip install -e .
redis-server
fastapi dev app/main.py
celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo
```

On Windows, `--pool=solo` is the safest option.

## Test endpoint

After logging in, start a demo task:

```bash
POST /api/tasks/demo?seconds=5
```

Then poll:

```bash
GET /api/tasks/{task_id}
```

Replace `demo_background_task` in `app/tasks.py` with real processing jobs later.
