#!/bin/bash
# ==============================================================================
# ElasticBot Backend - Docker Entrypoint Script
# ==============================================================================
# Prepares the application and starts supervisord to run all processes
# Processes: web (Gunicorn), worker (Celery), beat (Celery Beat)
# ==============================================================================

set -e

echo ""
echo "============================================================"
echo "🚀 ElasticBot Backend - Multi-Process Startup"
echo "============================================================"
echo "Time: $(date)"
echo "============================================================"
echo ""

# Wait for database to be ready
echo "📡 Checking database connection..."
MAX_RETRIES=30
RETRY_COUNT=0

while ! python manage.py check --database default 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Database connection failed after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "   Waiting for database... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done
echo "✅ Database connection OK"
echo ""

# Run migrations
echo "📦 Running database migrations..."
python manage.py migrate --noinput
echo "✅ Migrations complete"
echo ""

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null || true
echo "✅ Static files collected"
echo ""

# Show configuration
echo "============================================================"
echo "📋 Configuration:"
echo "   PORT: ${PORT:-8000}"
echo "   GUNICORN_WORKERS: ${GUNICORN_WORKERS:-4}"
echo "   CELERY_CONCURRENCY: ${CELERY_CONCURRENCY:-2}"
echo "   CELERY_LOG_LEVEL: ${CELERY_LOG_LEVEL:-info}"
echo "============================================================"
echo ""

echo "============================================================"
echo "🎬 Starting supervisord with 3 processes:"
echo "   1. 🌐 Web (Gunicorn) - HTTP API server"
echo "   2. ⚙️  Worker (Celery) - Async task processor"
echo "   3. ⏰ Beat (Celery Beat) - Scheduled task sender"
echo ""
echo "📅 Scheduled Tasks:"
echo "   - P2P Scrape: Every 30 min (XX:00, XX:30)"
echo "   - BCB Rate: Daily at 8:00 AM Bolivia"
echo "   - Cleanup: Weekly on Sundays"
echo "============================================================"
echo ""

# Execute the command passed to the container (supervisord by default)
exec "$@"
