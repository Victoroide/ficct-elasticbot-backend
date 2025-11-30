"""
Local Celery configuration for development when Redis is unavailable.
Uses filesystem transport instead of Redis.

Usage:
    # Terminal 1 - Worker:
    set CELERY_BROKER_URL=filesystem://
    celery -A base worker --loglevel=info

    # Terminal 2 - Beat:
    set CELERY_BROKER_URL=filesystem://
    celery -A base beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
"""
from base.celery import app
import os

# Set broker to filesystem before importing celery app
BROKER_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'celery_broker')
os.makedirs(os.path.join(BROKER_FOLDER, 'out'), exist_ok=True)
os.makedirs(os.path.join(BROKER_FOLDER, 'processed'), exist_ok=True)

# Override environment variables
os.environ['CELERY_BROKER_URL'] = 'filesystem://'
os.environ['CELERY_RESULT_BACKEND'] = 'django-db'

# Now import the app

# Configure filesystem transport
app.conf.broker_transport_options = {
    'data_folder_in': os.path.join(BROKER_FOLDER, 'out'),
    'data_folder_out': os.path.join(BROKER_FOLDER, 'out'),
    'processed_folder': os.path.join(BROKER_FOLDER, 'processed'),
}
