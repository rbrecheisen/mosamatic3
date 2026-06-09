FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1
ENV PATH="/app/mosamatic3/serveronly/.venv/bin:$PATH"

WORKDIR /app/mosamatic3/serveronly

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential curl dos2unix \
  && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* /app/mosamatic3/serveronly
RUN uv sync --no-dev --no-install-project
COPY . /app/mosamatic3/serveronly
RUN dos2unix \
  /app/mosamatic3/serveronly/docker/entrypoint-web.sh \
  /app/mosamatic3/serveronly/docker/entrypoint-worker.sh \
  /app/mosamatic3/serveronly/nginx/nginx.conf
RUN chmod +x /app/mosamatic3/serveronly/docker/entrypoint-web.sh /app/mosamatic3/serveronly/docker/entrypoint-worker.sh
RUN mkdir -p /data/uploads /data/staticfiles

EXPOSE 8000

CMD ["/app/mosamatic3/serveronly/docker/entrypoint-web.sh"]