#!/bin/bash
set -e
python manage.py wait_for_db
# Wait for migrations
python manage.py wait_for_migrations

python manage.py collectstatic --noinput

# Ensure service user for API-to-API auth exists
python manage.py ensure_service_user || true

exec gunicorn -w "$GUNICORN_WORKERS" -k uvicorn.workers.UvicornWorker api.asgi:application --bind 0.0.0.0:"${PORT:-8000}" --max-requests 1200 --max-requests-jitter 1000 --access-logfile -