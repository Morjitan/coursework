FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --only=main --no-root

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "overlay.main:app", "--host", "0.0.0.0", "--port", "8000"] 