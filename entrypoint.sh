#!/bin/sh
set -e

echo "==> Running collectstatic..."
python manage.py collectstatic --noinput

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 --workers 4 --threads 2 wine_project.wsgi:application
