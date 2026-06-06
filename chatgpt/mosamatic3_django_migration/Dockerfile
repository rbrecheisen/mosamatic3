FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update   && apt-get install -y --no-install-recommends build-essential   && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
RUN pip install --no-cache-dir -e .

COPY . /app/

RUN mkdir -p /data/uploads

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py ensure_admin && python manage.py runserver 0.0.0.0:8000"]
