"""
Celery tasks for async elasticity calculations.
"""
from celery import shared_task
from decimal import Decimal
from apps.elasticity.models import ElasticityCalculation
from apps.elasticity.services import (
    MidpointElasticityCalculator,
    RegressionElasticityCalculator
)
from apps.market_data.models import MarketSnapshot
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def calculate_elasticity_async(self, calculation_id: str):
    """
    Calculate elasticity asynchronously.

    Args:
        calculation_id: UUID of ElasticityCalculation record

    Returns:
        Dict with calculation results
    """
    try:
        calculation = ElasticityCalculation.objects.get(id=calculation_id)
        calculation.status = 'PROCESSING'
        calculation.save(update_fields=['status'])

        logger.info(f"Starting calculation {calculation_id}")

        # Fetch market data for period
        snapshots = MarketSnapshot.objects.filter(
            timestamp__gte=calculation.start_date,
            timestamp__lte=calculation.end_date,
            data_quality_score__gte=0.7  # Only high-quality data
        ).order_by('timestamp')

        if not snapshots.exists():
            raise ValueError("No market data available for specified period")

        # Extract prices and volumes
        prices = [Decimal(str(s.average_sell_price)) for s in snapshots]
        volumes = [Decimal(str(s.total_volume)) for s in snapshots]

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
                'avg_quality': sum(s.data_quality_score for s in snapshots) / len(snapshots),
                'min_quality': min(s.data_quality_score for s in snapshots),
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

    except Exception as exc:
        logger.error(
            f"Calculation {calculation_id} failed: {str(exc)}",
            exc_info=True
        )

        try:
            calculation = ElasticityCalculation.objects.get(id=calculation_id)
            calculation.mark_failed(str(exc))
        except Exception:
            pass

        raise self.retry(exc=exc, countdown=60)
