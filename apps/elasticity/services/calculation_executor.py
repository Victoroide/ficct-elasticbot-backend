"""
Elasticity calculation executor service.

This service contains the core calculation logic that can be executed
either synchronously (direct call) or asynchronously (via Celery task).

This separation allows:
- Sync mode: Direct execution when Redis/Celery are unavailable
- Async mode: Background processing via Celery when Redis is healthy

Usage:
    from apps.elasticity.services import execute_calculation
    
    # Execute calculation (returns result dict)
    result = execute_calculation(calculation_id)
"""
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
EXTERNAL_API_QUALITY_THRESHOLD = 0.95


def execute_calculation(calculation_id: str) -> dict:
    """
    Execute elasticity calculation synchronously.
    
    This is the core calculation logic extracted from the Celery task.
    Can be called directly for sync mode or from Celery task for async mode.
    
    Args:
        calculation_id: UUID string of the ElasticityCalculation record
        
    Returns:
        Dict with calculation results:
        - calculation_id: str
        - status: 'COMPLETED' | 'FAILED' | 'NOT_FOUND'
        - elasticity: float (if successful)
        - classification: str (if successful)
        - error: str (if failed)
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
                'end_date': calculation.end_date.isoformat(),
                'execution_mode': 'sync'
            }
        )

        # Ensure dates are timezone-aware and in UTC
        start_date_utc = _ensure_utc(calculation.start_date)
        end_date_utc = _ensure_utc(calculation.end_date)

        # Query high-quality OHLC data only
        snapshots = MarketSnapshot.objects.filter(
            timestamp__gte=start_date_utc,
            timestamp__lte=end_date_utc,
            data_quality_score__gte=EXTERNAL_API_QUALITY_THRESHOLD
        ).order_by('timestamp')

        snapshot_count = snapshots.count()
        
        logger.info(
            f"Query executed: {start_date_utc.date()} to {end_date_utc.date()}, "
            f"quality >= {EXTERNAL_API_QUALITY_THRESHOLD}, found {snapshot_count} snapshots",
            extra={
                'calculation_id': calculation_id,
                'snapshot_count': snapshot_count
            }
        )
        
        # Determine minimum required data points
        min_required = (
            MIN_DATA_POINTS_REGRESSION if calculation.method == 'REGRESSION' 
            else MIN_DATA_POINTS_MIDPOINT
        )

        # Validate sufficient data
        if snapshot_count == 0:
            _fail_calculation(
                calculation,
                f"No high-quality OHLC data available for {start_date_utc.date()} to {end_date_utc.date()}. "
                f"Only external API data (quality >= {EXTERNAL_API_QUALITY_THRESHOLD}) is used."
            )
            return {'calculation_id': calculation_id, 'status': 'FAILED', 'error': 'no_data'}

        if snapshot_count < min_required:
            _fail_calculation(
                calculation,
                f"Insufficient data points: found {snapshot_count}, need {min_required} for {calculation.method}."
            )
            return {'calculation_id': calculation_id, 'status': 'FAILED', 'error': 'insufficient_data'}

        # Extract prices and volumes
        snapshot_list = list(snapshots)
        prices = [Decimal(str(s.average_sell_price)) for s in snapshot_list]
        volumes = [Decimal(str(s.total_volume)) if s.total_volume else Decimal('0') for s in snapshot_list]

        # Calculate based on method
        try:
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
        except ValueError as e:
            # Validation error (e.g., insufficient price variation)
            _fail_calculation(calculation, str(e))
            return {'calculation_id': calculation_id, 'status': 'FAILED', 'error': str(e)}

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

        # Store reliability at top level for easy API access
        calculation.is_reliable = result.get('is_reliable', True)
        calculation.reliability_note = result.get('reliability_note')

        # Store detailed metadata
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
            'price_quantity_changes': {
                'percentage_change_price': result.get('percentage_change_price'),
                'percentage_change_quantity': result.get('percentage_change_quantity'),
                'price_change': result.get('price_change'),
                'quantity_change': result.get('quantity_change'),
            },
            'volume_disclaimer': (
                "Note: 'quantity' is derived from P2P total_volume (advertised offers), "
                "not actual traded volume. This is a proxy for market activity, "
                "not pure demand. High elasticity values may reflect liquidity "
                "fluctuations rather than true price responsiveness."
            ),
            'execution_mode': 'sync',
        }

        calculation.average_data_quality = calculation.calculation_metadata['data_quality']['avg_quality']
        
        # Save all computed fields
        calculation.save(update_fields=[
            'elasticity_coefficient',
            'classification',
            'data_points_used',
            'confidence_interval_lower',
            'confidence_interval_upper',
            'r_squared',
            'standard_error',
            'is_reliable',
            'reliability_note',
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
            'status': 'COMPLETED',
            'elasticity': result['elasticity'],
            'classification': result['classification']
        }

    except ElasticityCalculation.DoesNotExist:
        logger.error(f"Calculation {calculation_id} not found")
        return {'calculation_id': calculation_id, 'status': 'NOT_FOUND', 'error': 'record_not_found'}

    except Exception as exc:
        logger.error(
            f"Calculation {calculation_id} failed: {str(exc)}",
            exc_info=True,
            extra={'calculation_id': calculation_id}
        )

        if calculation is not None:
            try:
                _fail_calculation(calculation, f"Calculation error: {str(exc)}")
            except Exception as save_exc:
                logger.error(f"Failed to save error state: {save_exc}")

        return {'calculation_id': calculation_id, 'status': 'FAILED', 'error': str(exc)}


def _ensure_utc(dt):
    """Ensure datetime is timezone-aware and in UTC."""
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt.astimezone(dt_timezone.utc)


def _fail_calculation(calculation, error_message: str):
    """Mark calculation as failed."""
    calculation.status = 'FAILED'
    calculation.error_message = error_message
    calculation.completed_at = timezone.now()
    calculation.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
    
    logger.warning(
        f"Calculation {calculation.id} FAILED: {error_message}",
        extra={'calculation_id': str(calculation.id)}
    )
