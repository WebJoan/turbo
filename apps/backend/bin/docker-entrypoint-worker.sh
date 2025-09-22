#!/bin/bash
set -e

python manage.py wait_for_db
# Wait for migrations
python manage.py wait_for_migrations

# Ensure Playwright browsers are installed (fallback)
python -m playwright install chromium --with-deps || echo "Playwright browsers already installed or installation failed"

# Run the processes
celery -A api worker -l info