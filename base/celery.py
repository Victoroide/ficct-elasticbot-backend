import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')

app = Celery('elasticbot')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Market data collection - every 30 minutes for better granularity
    'fetch-binance-p2p-frequent': {
        'task': 'apps.market_data.tasks.fetch_binance_data',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'options': {'expires': 1500},  # Task expires after 25 minutes
    },
    # BCB official rate - daily at 8 AM Bolivia time (UTC-4)
    'fetch-bcb-exchange-rate-daily': {
        'task': 'apps.market_data.tasks.fetch_bcb_exchange_rate',
        'schedule': crontab(hour=12, minute=0),  # 8 AM Bolivia = 12:00 UTC
    },
    # Data cleanup - weekly on Sundays at 3 AM
    'cleanup-old-snapshots': {
        'task': 'apps.market_data.tasks.cleanup_old_data',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
