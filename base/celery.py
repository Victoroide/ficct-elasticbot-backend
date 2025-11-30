import os
import logging
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready, beat_init

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')

logger = logging.getLogger(__name__)

app = Celery('elasticbot')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Log when Celery worker is ready to accept tasks."""
    logger.info("=" * 60)
    logger.info("⚙️  CELERY WORKER READY")
    logger.info(f"   Hostname: {sender.hostname}")
    logger.info(f"   Concurrency: {sender.concurrency}")
    logger.info(f"   Broker: {app.conf.broker_url}")
    logger.info("=" * 60)


@beat_init.connect
def on_beat_init(sender, **kwargs):
    """Log when Celery beat scheduler starts."""
    logger.info("=" * 60)
    logger.info("⏰ CELERY BEAT SCHEDULER INITIALIZED")
    logger.info("   Scheduled tasks:")
    for task_name, task_config in app.conf.beat_schedule.items():
        schedule = task_config.get('schedule', 'unknown')
        logger.info(f"   - {task_name}: {schedule}")
    logger.info("=" * 60)

# =============================================================================
# CELERY BEAT SCHEDULE
# =============================================================================
# NOTE: The external OHLC API is NOT called by any scheduled task.
# External API data was imported once via manual command and is used exclusively
# for elasticity calculations (filtered by data_quality_score >= 0.95).
#
# The P2P scraper below collects data for monitoring purposes only.
# Its data (quality ~0.8) is automatically excluded from elasticity calculations.
# =============================================================================
app.conf.beat_schedule = {
    # P2P Scraper - for market monitoring (NOT used in elasticity calculations)
    # Data quality ~0.8 is filtered out by elasticity engine (requires >= 0.95)
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
