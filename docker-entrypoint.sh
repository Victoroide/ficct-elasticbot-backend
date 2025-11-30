#!/bin/bash
# ==============================================================================
# ElasticBot Backend - Docker Entrypoint Script
# ==============================================================================
# Flexible entrypoint that can start web, worker, or beat based on SERVICE_TYPE
# Usage in Railway: Set SERVICE_TYPE env var to "web", "worker", or "beat"
# ==============================================================================

set -e

# Default to web if no service type specified
SERVICE_TYPE="${SERVICE_TYPE:-web}"

echo "=============================================="
echo "ElasticBot Backend - Starting ${SERVICE_TYPE}"
echo "=============================================="

# Wait for database to be ready
echo "Checking database connection..."
python manage.py check --database default 2>/dev/null || {
    echo "Waiting for database..."
    sleep 5
    python manage.py check --database default
}

# Run migrations only for web service (avoid race conditions)
if [ "$SERVICE_TYPE" = "web" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput
    
    echo "Collecting static files..."
    python manage.py collectstatic --noinput --clear 2>/dev/null || true
fi

# Start the appropriate service
case "$SERVICE_TYPE" in
    web)
        echo "Starting Gunicorn web server..."
        exec gunicorn base.wsgi:application \
            --bind 0.0.0.0:${PORT:-8000} \
            --workers ${GUNICORN_WORKERS:-4} \
            --timeout ${GUNICORN_TIMEOUT:-120} \
            --access-logfile - \
            --error-logfile - \
            --capture-output \
            --enable-stdio-inheritance
        ;;
    
    worker)
        echo "Starting Celery worker..."
        exec celery -A base worker \
            --loglevel=${CELERY_LOG_LEVEL:-info} \
            --concurrency=${CELERY_CONCURRENCY:-2}
        ;;
    
    beat)
        echo "Starting Celery beat scheduler..."
        exec celery -A base beat \
            --loglevel=${CELERY_LOG_LEVEL:-info} \
            --scheduler django_celery_beat.schedulers:DatabaseScheduler
        ;;
    
    flower)
        echo "Starting Flower monitoring..."
        exec celery -A base flower \
            --port=${FLOWER_PORT:-5555}
        ;;
    
    *)
        echo "Unknown SERVICE_TYPE: $SERVICE_TYPE"
        echo "Valid options: web, worker, beat, flower"
        exit 1
        ;;
esac
