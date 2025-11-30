"""
Celery tasks for async elasticity calculations.

==============================================================================
DATA SOURCE SEPARATION - CRITICAL DESIGN DECISION
==============================================================================

Elasticity calculations use ONLY high-quality data from the external OHLC API
(source='external_ohlc_api', data_quality_score >= 0.95). This ensures:

1. CONSISTENT, RELIABLE price data from Binance exchange
2. NO MIXING of scraped P2P data with exchange OHLC data
3. num_active_traders is NOT used in any calculation (always 0 for external data)

Historical P2P scrapes (source='p2p_scrape_json', quality=0.80) are EXCLUDED
from elasticity calculations by design. They are stored for:
- Visualization in the "Historial de Precios" chart
- Historical context and exploratory analysis
- Data comparison and validation

The quality threshold (0.95) acts as a strict filter that automatically
excludes all P2P data (0.80) from elasticity calculations.

The external API was called once to populate historical data. The system now
operates entirely on local database records without external API dependencies.
==============================================================================
"""
from celery import shared_task
from decimal import Decimal
from datetime import timezone as dt_timezone
from django.utils import timezone
from apps.elasticity.models import ElasticityCalculation
from apps.elasticity.services import (
    MidpointElasticityCalculator,
    RegressionElasticityCalculator
)
from apps.market_data.models import MarketSnapshot
import logging

logger = logging.getLogger(__name__)

# Minimum data points required for each calculation method
MIN_DATA_POINTS_MIDPOINT = 2
MIN_DATA_POINTS_REGRESSION = 5

# Quality threshold for external OHLC API data
# Only data with this score is used in calculations (filters out old/scraped data)
EXTERNAL_API_QUALITY_THRESHOLD = 0.95


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def calculate_elasticity_async(self, calculation_id: str):
    """
    Calculate elasticity asynchronously.

    Args:
        calculation_id: UUID of ElasticityCalculation record

    Returns:
        Dict with calculation results
    """
    calculation = None
    try:
        calculation = ElasticityCalculation.objects.get(id=calculation_id)
        calculation.status = 'PROCESSING'
        calculation.save(update_fields=['status', 'updated_at'])

        logger.info(
            f"Starting calculation {calculation_id}",
            extra={
                'calculation_id': calculation_id,
                'method': calculation.method,
                'start_date': calculation.start_date.isoformat(),
                'end_date': calculation.end_date.isoformat()
            }
        )

        # Ensure dates are timezone-aware and in UTC for consistent querying
        start_date_utc = _ensure_utc(calculation.start_date)
        end_date_utc = _ensure_utc(calculation.end_date)

        logger.debug(
            f"Query range (UTC): {start_date_utc} to {end_date_utc}",
            extra={'start_utc': start_date_utc.isoformat(), 'end_utc': end_date_utc.isoformat()}
        )

        # ==================================================================
        # STRICT FILTER: External OHLC API data ONLY
        # ==================================================================
        # This filter ensures elasticity calculations use ONLY:
        # - source='external_ohlc_api' (high-quality exchange data)
        # - data_quality_score >= 0.95
        #
        # EXCLUDED by design:
        # - source='p2p_scrape_json' (historical P2P scrapes, quality=0.80)
        #   These are for visualization only, not for elasticity calculations.
        # ==================================================================
        snapshots = MarketSnapshot.objects.filter(
            timestamp__gte=start_date_utc,
            timestamp__lte=end_date_utc,
            data_quality_score__gte=EXTERNAL_API_QUALITY_THRESHOLD  # Only external API data (0.95+)
        ).order_by('timestamp')

        snapshot_count = snapshots.count()

        logger.info(
            f"Query executed: {start_date_utc.date()} to {end_date_utc.date()}, "
            f"quality >= {EXTERNAL_API_QUALITY_THRESHOLD}, found {snapshot_count} snapshots",
            extra={
                'calculation_id': calculation_id,
                'start_date': start_date_utc.isoformat(),
                'end_date': end_date_utc.isoformat(),
                'quality_threshold': EXTERNAL_API_QUALITY_THRESHOLD,
                'snapshot_count': snapshot_count
            }
        )

        # Determine minimum required data points based on method
        min_required = (
            MIN_DATA_POINTS_REGRESSION if calculation.method == 'REGRESSION'
            else MIN_DATA_POINTS_MIDPOINT
        )

        # Validate sufficient data points - fail explicitly if insufficient
        if snapshot_count == 0:
            _fail_calculation(
                calculation,
                f"No high-quality OHLC data available for the period {start_date_utc.date()} to {end_date_utc.date()}. "
                f"Only external API data (quality >= {EXTERNAL_API_QUALITY_THRESHOLD}) is used for calculations. "
                f"Check that imported data covers this date range."
            )
            return {'calculation_id': calculation_id, 'status': 'FAILED', 'error': 'no_data'}

        if snapshot_count < min_required:
            _fail_calculation(
                calculation,
                f"Insufficient high-quality data points: found {snapshot_count}, but {calculation.method} method "
                f"requires at least {min_required}. Try expanding the date range or using a different method."
            )
            return {'calculation_id': calculation_id, 'status': 'FAILED', 'error': 'insufficient_data'}

        logger.info(
            f"Found {snapshot_count} high-quality data points for calculation {calculation_id}",
            extra={'calculation_id': calculation_id, 'snapshot_count': snapshot_count}
        )

        # Extract prices and volumes (materialize queryset once)
        snapshot_list = list(snapshots)
        prices = [Decimal(str(s.average_sell_price)) for s in snapshot_list]
        volumes = [Decimal(str(s.total_volume)) for s in snapshot_list]

        # Calculate based on method
        if calculation.method == 'MIDPOINT':
            calculator = MidpointElasticityCalculator()
            result = calculator.calculate(
                quantity_initial=volumes[0],
                quantity_final=volumes[-1],
                price_initial=prices[0],
                price_final=prices[-1]
            )
        else:  # REGRESSION
            calculator = RegressionElasticityCalculator()
            result = calculator.calculate(prices, volumes)

        # Update calculation with results
        calculation.elasticity_coefficient = Decimal(str(result['elasticity']))
        calculation.classification = result['classification'].upper()
        calculation.data_points_used = len(prices)

        if 'confidence_interval_95' in result:
            ci = result['confidence_interval_95']
            calculation.confidence_interval_lower = Decimal(str(ci[0]))
            calculation.confidence_interval_upper = Decimal(str(ci[1]))

        if 'r_squared' in result:
            calculation.r_squared = Decimal(str(result['r_squared']))

        if 'standard_error' in result:
            calculation.standard_error = Decimal(str(result['standard_error']))

        # Store metadata - includes data source and quality filtering information
        calculation.calculation_metadata = {
            'method_details': result.get('metadata', {}),
            'data_quality': {
                'avg_quality': sum(s.data_quality_score for s in snapshot_list) / len(snapshot_list),
                'min_quality': min(s.data_quality_score for s in snapshot_list),
                'quality_threshold': EXTERNAL_API_QUALITY_THRESHOLD,
            },
            'query_info': {
                'start_date_utc': start_date_utc.isoformat(),
                'end_date_utc': end_date_utc.isoformat(),
                'snapshots_found': snapshot_count,
            },
            'data_source': {
                'type': 'external_ohlc_api',
                'description': 'High-quality OHLC data from Binance exchange via external API',
                'note': 'num_active_traders not used (always 0 for external data)',
            }
        }

        calculation.average_data_quality = calculation.calculation_metadata['data_quality']['avg_quality']

        # Save all computed fields before marking completed
        calculation.save(update_fields=[
            'elasticity_coefficient',
            'classification',
            'data_points_used',
            'confidence_interval_lower',
            'confidence_interval_upper',
            'r_squared',
            'standard_error',
            'calculation_metadata',
            'average_data_quality',
            'updated_at'
        ])
        calculation.mark_completed()

        logger.info(
            f"Completed calculation {calculation_id}: {result['elasticity']:.4f}",
            extra={'calculation_id': calculation_id, 'elasticity': result['elasticity']}
        )

        return {
            'calculation_id': calculation_id,
            'elasticity': result['elasticity'],
            'classification': result['classification']
        }

    except ElasticityCalculation.DoesNotExist:
        logger.error(
            f"Calculation {calculation_id} not found in database",
            extra={'calculation_id': calculation_id}
        )
        # Don't retry - record doesn't exist
        return {'calculation_id': calculation_id, 'status': 'NOT_FOUND', 'error': 'record_not_found'}

    except Exception as exc:
        logger.error(
            f"Calculation {calculation_id} failed: {str(exc)}",
            exc_info=True,
            extra={'calculation_id': calculation_id, 'exception_type': type(exc).__name__}
        )

        # Mark as failed if we have the calculation object
        if calculation is not None:
            try:
                _fail_calculation(calculation, f"Calculation error: {str(exc)}")
            except Exception as save_exc:
                logger.error(f"Failed to save error state: {save_exc}")

        # Only retry for transient errors, not business logic failures
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

        return {'calculation_id': calculation_id, 'status': 'FAILED', 'error': str(exc)}


def _ensure_utc(dt):
    """
    Ensure a datetime is timezone-aware and converted to UTC.

    This handles the case where dates come in without timezone info
    or in a different timezone than UTC.
    """
    if dt is None:
        return None

    # If naive, assume it's in the default timezone and make it aware
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)

    # Convert to UTC for consistent database querying
    return dt.astimezone(dt_timezone.utc)


def _fail_calculation(calculation, error_message: str):
    """
    Mark a calculation as failed with a descriptive error message.

    This ensures failed calculations are never left in PENDING/PROCESSING state.
    """
    calculation.status = 'FAILED'
    calculation.error_message = error_message
    calculation.completed_at = timezone.now()
    calculation.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])

    logger.warning(
        f"Calculation {calculation.id} marked as FAILED: {error_message}",
        extra={'calculation_id': str(calculation.id), 'error_message': error_message}
    )
