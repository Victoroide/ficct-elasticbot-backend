web: gunicorn base.wsgi --bind 0.0.0.0:$PORT --workers 4 --timeout 120
worker: celery -A base worker -l info --concurrency=2
beat: celery -A base beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
