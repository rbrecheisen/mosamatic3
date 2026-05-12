# FastAPI + React Template App

Small starter project with:

- FastAPI REST API
- React + Vite frontend
- Account registration and login using JWT bearer tokens
- SQLite database via SQLModel
- File upload and folder upload from the browser
- Example form widgets stored in SQLite
- Docker Compose setup

## Project structure

```text
fastapi-react-template/
├─ backend/
│  ├─ app/
│  │  ├─ auth.py
│  │  ├─ config.py
│  │  ├─ database.py
│  │  ├─ main.py
│  │  ├─ models.py
│  │  └─ schemas.py
│  ├─ data/
│  │  └─ uploads/
│  ├─ Dockerfile
│  ├─ .env.example
│  └─ pyproject.toml
├─ frontend/
│  ├─ src/
│  │  ├─ api/client.ts
│  │  ├─ components/
│  │  ├─ App.tsx
│  │  ├─ main.tsx
│  │  └─ styles.css
│  ├─ Dockerfile
│  ├─ nginx.conf
│  ├─ package.json
│  └─ vite.config.ts
└─ docker-compose.yml
```

## Run locally without Docker

### Backend

```bash
cd backend
cp .env.example .env
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
fastapi dev app/main.py
```

Backend runs at:

```text
http://localhost:8000
```

API docs:

```text
http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at:

```text
http://localhost:5173
```

The Vite dev server proxies `/api` calls to `http://localhost:8000`.

## Run with Docker Compose

```bash
docker compose up --build
```

Frontend:

```text
http://localhost:5173
```

Backend:

```text
http://localhost:8000
```

SQLite DB and uploads are stored in the Docker volume `backend_data`.

## Upload behavior

The frontend has two upload buttons:

- **Upload files**: lets the user select one or more files.
- **Upload directory**: uses the browser's `webkitdirectory` capability to upload a folder tree.

The backend stores files under:

```text
backend/data/uploads/<user-id>/...
```

For folder uploads, relative paths are preserved, while `../` traversal is blocked.

## Main API endpoints

```text
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
POST /api/uploads
POST /api/forms
GET  /api/forms
GET  /api/health
```

## Notes for adapting this template

- Replace `SECRET_KEY` in production.
- Add max upload size limits before using this for untrusted users.
- Add database migrations, e.g. Alembic, once the schema starts changing.
- Use PostgreSQL instead of SQLite if multiple users/processes will write heavily.
- For medical/local Docker workflows, mount a host folder into `/app/data` if you want uploads and the database visible outside the container.
