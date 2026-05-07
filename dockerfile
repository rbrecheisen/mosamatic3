FROM python:3.12-slim
WORKDIR /mosamatic3
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY src/main.py .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]