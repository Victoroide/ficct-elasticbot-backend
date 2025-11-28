"""
Data validation and quality assessment for market snapshots.
"""
from decimal import Decimal
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """
    Validates market data quality and calculates quality scores.

    Quality factors:
    - Price within expected range (6.00 - 8.00 BOB)
    - Sufficient trading volume (>100 USDT)
    - Reasonable number of traders (>5)
    - Spread not too wide (<5%)
    """

    MIN_PRICE = Decimal('5.00')
    MAX_PRICE = Decimal('15.00')
    MIN_VOLUME = Decimal('100')
    MIN_TRADERS = 5
    MAX_SPREAD = Decimal('5.0')  # 5%

    @classmethod
    def calculate_quality_score(cls, snapshot_data: Dict) -> float:
        """
        Calculate data quality score (0.0 - 1.0).

        Args:
            snapshot_data: Dictionary with market metrics

        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 1.0

        # Check price range
        price = Decimal(str(snapshot_data.get('average_sell_price', 0)))
        if not (cls.MIN_PRICE <= price <= cls.MAX_PRICE):
            score -= 0.3
            logger.warning(f"Price {price} outside expected range")

        # Check volume
        volume = Decimal(str(snapshot_data.get('total_volume', 0)))
        if volume < cls.MIN_VOLUME:
            score -= 0.3
            logger.warning(f"Volume {volume} below minimum")

        # Check trader count
        traders = snapshot_data.get('num_active_traders', 0)
        if traders < cls.MIN_TRADERS:
            score -= 0.2
            logger.warning(f"Only {traders} traders active")

        # Check spread
        spread = Decimal(str(snapshot_data.get('spread_percentage', 0)))
        if spread > cls.MAX_SPREAD:
            score -= 0.2
            logger.warning(f"Spread {spread}% too wide")

        final_score = max(0.0, score)
        logger.info(f"Data quality score: {final_score:.2f}")

        return final_score

    @classmethod
    def is_valid(cls, snapshot_data: Dict) -> bool:
        """
        Check if snapshot meets minimum quality standards.

        Returns:
            True if quality score >= 0.7
        """
        score = cls.calculate_quality_score(snapshot_data)
        return score >= 0.7
