"""
Celery tasks for market data collection.

IMPORTANT: P2P scraper is scheduled every 30 minutes via Celery Beat.
Task has built-in protections against spam:
1. Minimum interval check (15 minutes between snapshots)
2. Redis lock to prevent concurrent execution
"""
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from apps.market_data.models import MarketSnapshot, DataCollectionLog
from apps.market_data.services import BinanceP2PService, DataValidator
import logging

logger = logging.getLogger(__name__)

# Minimum time between P2P snapshots (prevents spam)
MIN_SNAPSHOT_INTERVAL_MINUTES = 15

# Lock timeout for task execution (prevents concurrent runs)
TASK_LOCK_TIMEOUT_SECONDS = 300  # 5 minutes


@shared_task(bind=True, max_retries=3)
def fetch_binance_data(self):
    """
    Fetch current market data from Binance P2P.

    Scheduled to run every 30 minutes via Celery Beat.
    Creates MarketSnapshot record with current prices and volumes.
    
    PROTECTIONS:
    - Redis lock prevents concurrent execution
    - Minimum interval check prevents spam (15 min between snapshots)
    """
    start_time = timezone.now()
    lock_key = 'lock:fetch_binance_data'

    # =========================================================================
    # PROTECTION 1: Acquire exclusive lock (prevent concurrent execution)
    # =========================================================================
    try:
        lock_acquired = cache.add(lock_key, 'locked', TASK_LOCK_TIMEOUT_SECONDS)
        if not lock_acquired:
            logger.warning(
                "fetch_binance_data skipped: another instance is already running"
            )
            return {'status': 'skipped', 'reason': 'lock_not_acquired'}
    except Exception as e:
        # Cache unavailable - proceed without lock (better than failing completely)
        logger.warning(f"Cache unavailable for lock, proceeding anyway: {e}")
        lock_acquired = False  # Will skip release later

    try:
        # =====================================================================
        # PROTECTION 2: Check minimum interval since last snapshot
        # =====================================================================
        min_interval = timedelta(minutes=MIN_SNAPSHOT_INTERVAL_MINUTES)
        recent_cutoff = start_time - min_interval
        
        recent_snapshot = MarketSnapshot.objects.filter(
            timestamp__gte=recent_cutoff,
            data_quality_score__lt=0.95  # Only check P2P data, not OHLC
        ).order_by('-timestamp').first()

        if recent_snapshot:
            time_since_last = start_time - recent_snapshot.timestamp
            logger.info(
                f"fetch_binance_data skipped: last snapshot was {time_since_last.total_seconds():.0f}s ago "
                f"(minimum interval: {MIN_SNAPSHOT_INTERVAL_MINUTES} minutes)"
            )
            return {
                'status': 'skipped',
                'reason': 'too_recent',
                'last_snapshot_id': recent_snapshot.pk,
                'seconds_since_last': time_since_last.total_seconds()
            }

        logger.info("Starting Binance P2P data collection")

        # Fetch data from Binance
        service = BinanceP2PService()
        snapshot_data = service.calculate_market_snapshot()

        # Calculate quality score
        quality_score = DataValidator.calculate_quality_score(snapshot_data)

        # Create snapshot record
        snapshot = MarketSnapshot.objects.create(
            timestamp=start_time,
            average_sell_price=snapshot_data['average_sell_price'],
            average_buy_price=snapshot_data['average_buy_price'],
            total_volume=snapshot_data['total_volume'],
            spread_percentage=snapshot_data['spread_percentage'],
            num_active_traders=snapshot_data['num_active_traders'],
            data_quality_score=quality_score,
            raw_response=snapshot_data['raw_data']
        )

        # Log success
        execution_time = int((timezone.now() - start_time).total_seconds() * 1000)
        DataCollectionLog.objects.create(
            source='Binance P2P',
            status='SUCCESS',
            records_created=1,
            execution_time_ms=execution_time
        )

        logger.info(
            f"Successfully collected Binance data: {snapshot.average_sell_price} BOB, "
            f"Volume: {snapshot.total_volume}, Quality: {quality_score:.2f}"
        )

        return {
            'status': 'success',
            'snapshot_id': snapshot.pk,
            'price': float(snapshot.average_sell_price),
            'volume': float(snapshot.total_volume),
            'quality_score': quality_score
        }

    except Exception as exc:
        logger.error(f"Binance data collection failed: {exc}", exc_info=True)

        # Log failure
        execution_time = int((timezone.now() - start_time).total_seconds() * 1000)
        DataCollectionLog.objects.create(
            source='Binance P2P',
            status='FAILED',
            records_created=0,
            error_message=str(exc),
            execution_time_ms=execution_time
        )

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

    finally:
        # Release the lock if we acquired it
        if lock_acquired:
            try:
                cache.delete(lock_key)
            except Exception as e:
                logger.warning(f"Failed to release lock: {e}")


@shared_task
def cleanup_old_data():
    """
    Delete market snapshots older than 90 days.

    Scheduled to run weekly via Celery Beat.
    Helps maintain database performance and comply with data retention policies.
    """
    cutoff_date = timezone.now() - timedelta(days=90)

    deleted_count, _ = MarketSnapshot.objects.filter(
        created_at__lt=cutoff_date
    ).delete()

    logger.info(f"Cleaned up {deleted_count} old market snapshots")

    return {'deleted_count': deleted_count, 'cutoff_date': cutoff_date.isoformat()}


@shared_task(bind=True, max_retries=3)
def fetch_bcb_exchange_rate(self):
    """
    Fetch official BOB/USD exchange rate from BCB (Banco Central de Bolivia).

    Scheduled to run daily at 8:00 AM Bolivia time.
    Implements retry logic with exponential backoff.

    The official BOB/USD rate has been fixed at ~6.96 since 2011.
    This task tracks the rate for historical records and detects any changes.

    Returns:
        dict: {
            'status': 'success' | 'failed',
            'rate': float,
            'date': str (ISO format),
            'source': str,
            'created': bool (True if new record, False if updated)
        }
    """
    from apps.market_data.services.bcb_service import get_bcb_service
    from apps.market_data.models import MacroeconomicIndicator

    start_time = timezone.now()
    logger.info("Starting BCB exchange rate fetch")

    try:
        # Fetch rate from BCB
        bcb_service = get_bcb_service()
        result = bcb_service.fetch_exchange_rate()

        if not result['success']:
            logger.error(f"BCB fetch failed: {result.get('error')}")
            raise Exception(result.get('error', 'Unknown BCB fetch error'))

        rate = result['rate']
        rate_date = result['date']
        source = result['source']

        # Check if record exists for today
        indicator, created = MacroeconomicIndicator.objects.update_or_create(
            date=rate_date,
            defaults={
                'official_exchange_rate': rate,
                'source': 'BCB',
                'raw_data': result.get('raw_data', {})
            }
        )

        # Log collection event
        execution_time = int((timezone.now() - start_time).total_seconds() * 1000)
        DataCollectionLog.objects.create(
            source='BCB',
            status='SUCCESS',
            records_created=1 if created else 0,
            execution_time_ms=execution_time
        )

        action = 'created' if created else 'updated'
        logger.info(
            f"BCB exchange rate {action}: {rate} BOB/USD for {rate_date} "
            f"(source: {source})"
        )

        return {
            'status': 'success',
            'rate': float(rate),
            'date': rate_date.isoformat(),
            'source': source,
            'created': created
        }

    except Exception as exc:
        logger.error(f"BCB exchange rate fetch failed: {exc}", exc_info=True)

        # Log failure
        execution_time = int((timezone.now() - start_time).total_seconds() * 1000)
        DataCollectionLog.objects.create(
            source='BCB',
            status='FAILED',
            records_created=0,
            error_message=str(exc),
            execution_time_ms=execution_time
        )

        # Retry with exponential backoff (60s, 120s, 240s)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
