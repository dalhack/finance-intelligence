FROM python:3.12-slim

WORKDIR /app

COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY services ./services
COPY packages ./packages

# app.* imports resolve via services/api; services.api.app.main via repo root
ENV PYTHONPATH=/app:/app/services/api
ENV PYTHONUNBUFFERED=1

CMD exec uvicorn services.api.app.main:app --host 0.0.0.0 --port ${PORT:-8080}
