FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential curl dos2unix \
  && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* /app/
RUN uv sync --no-dev --no-install-project
COPY . /app/
RUN dos2unix \
  /app/docker/entrypoint-web.sh \
  /app/docker/entrypoint-worker.sh \
  /app/nginx/nginx.conf
RUN chmod +x /app/docker/entrypoint-web.sh /app/docker/entrypoint-worker.sh
RUN mkdir -p /data/uploads /staticfiles

EXPOSE 8000

CMD ["/app/docker/entrypoint-web.sh"]