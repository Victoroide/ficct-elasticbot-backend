# Web process - Django application
web: gunicorn base.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile -

# Celery worker - processes async tasks (elasticity calculations, scraper, etc.)
worker: celery -A base worker -l info --concurrency=2 -E

# Celery beat - schedules periodic tasks (scraper every 30min, BCB daily, cleanup weekly)
beat: celery -A base beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
