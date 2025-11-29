"""
Celery tasks for async elasticity calculations.
"""
from celery import shared_task
from decimal import Decimal
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

        # Fetch market data for period
        snapshots = MarketSnapshot.objects.filter(
            timestamp__gte=start_date_utc,
            timestamp__lte=end_date_utc,
            data_quality_score__gte=0.7  # Only high-quality data
        ).order_by('timestamp')

        snapshot_count = snapshots.count()
        
        # Determine minimum required data points based on method
        min_required = (
            MIN_DATA_POINTS_REGRESSION if calculation.method == 'REGRESSION' 
            else MIN_DATA_POINTS_MIDPOINT
        )

        # Validate sufficient data points - fail explicitly if insufficient
        if snapshot_count == 0:
            _fail_calculation(
                calculation,
                f"No market data available for the period {start_date_utc.date()} to {end_date_utc.date()}. "
                f"Please verify data exists and meets quality threshold (score >= 0.7)."
            )
            return {'calculation_id': calculation_id, 'status': 'FAILED', 'error': 'no_data'}

        if snapshot_count < min_required:
            _fail_calculation(
                calculation,
                f"Insufficient data points: found {snapshot_count}, but {calculation.method} method "
                f"requires at least {min_required}. Try expanding the date range or using a different method."
            )
            return {'calculation_id': calculation_id, 'status': 'FAILED', 'error': 'insufficient_data'}

        logger.info(
            f"Found {snapshot_count} data points for calculation {calculation_id}",
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

        # Store metadata
        calculation.calculation_metadata = {
            'method_details': result.get('metadata', {}),
            'data_quality': {
                'avg_quality': sum(s.data_quality_score for s in snapshot_list) / len(snapshot_list),
                'min_quality': min(s.data_quality_score for s in snapshot_list),
            },
            'query_info': {
                'start_date_utc': start_date_utc.isoformat(),
                'end_date_utc': end_date_utc.isoformat(),
                'snapshots_found': snapshot_count,
            }
        }

        calculation.average_data_quality = calculation.calculation_metadata['data_quality']['avg_quality']
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
    return dt.astimezone(timezone.utc)


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
