from decimal import Decimal
from django.core.exceptions import ValidationError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PriceValidator:
    """Validates USDT/BOB price data."""

    MIN_PRICE = Decimal('5.00')
    MAX_PRICE = Decimal('15.00')

    @staticmethod
    def validate_price(price: Decimal) -> bool:
        """
        Validate if price is within acceptable range.

        Args:
            price: USDT/BOB price to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If price is out of range
        """
        if not isinstance(price, Decimal):
            price = Decimal(str(price))

        if price < PriceValidator.MIN_PRICE or price > PriceValidator.MAX_PRICE:
            raise ValidationError(
                f"Price {price} is outside acceptable range "
                f"[{PriceValidator.MIN_PRICE}, {PriceValidator.MAX_PRICE}]"
            )

        return True


class VolumeValidator:
    """Validates trading volume data."""

    MIN_VOLUME = Decimal('100.00')

    @staticmethod
    def validate_volume(volume: Decimal) -> bool:
        """
        Validate if volume meets minimum threshold.

        Args:
            volume: Trading volume to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If volume is too low
        """
        if not isinstance(volume, Decimal):
            volume = Decimal(str(volume))

        if volume < VolumeValidator.MIN_VOLUME:
            raise ValidationError(
                f"Volume {volume} is below minimum threshold "
                f"{VolumeValidator.MIN_VOLUME}"
            )

        return True


class OutlierDetector:
    """Detects statistical outliers in price/volume data."""

    Z_SCORE_THRESHOLD = 3.0

    @staticmethod
    def detect_outlier(value: float, mean: float, std: float) -> bool:
        """
        Detect if value is a statistical outlier using Z-score.

        Args:
            value: Value to check
            mean: Mean of dataset
            std: Standard deviation of dataset

        Returns:
            True if outlier detected
        """
        if std == 0:
            return False

        z_score = abs((value - mean) / std)

        if z_score > OutlierDetector.Z_SCORE_THRESHOLD:
            logger.warning(
                f"Outlier detected: value={value}, z_score={z_score:.2f}"
            )
            return True

        return False


class DateRangeValidator:
    """Validates date ranges for data queries."""

    MAX_RANGE_DAYS = 365

    @staticmethod
    def validate_date_range(start_date: datetime, end_date: datetime) -> bool:
        """
        Validate if date range is acceptable.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            True if valid

        Raises:
            ValidationError: If date range is invalid
        """
        if start_date >= end_date:
            raise ValidationError("start_date must be before end_date")

        delta = end_date - start_date

        if delta.days > DateRangeValidator.MAX_RANGE_DAYS:
            raise ValidationError(
                f"Date range cannot exceed {DateRangeValidator.MAX_RANGE_DAYS} days. "
                f"Requested: {delta.days} days"
            )

        if end_date > datetime.now():
            raise ValidationError("end_date cannot be in the future")

        return True


class ElasticityValidator:
    """Validates elasticity calculation parameters and results."""

    MAX_ELASTICITY = Decimal('10.0')
    MIN_DATA_POINTS = 10
    MIN_TIME_WINDOW_HOURS = 6

    @staticmethod
    def validate_elasticity_result(elasticity: Decimal) -> bool:
        """
        Validate if calculated elasticity is reasonable.

        Args:
            elasticity: Calculated elasticity coefficient

        Returns:
            True if valid

        Raises:
            ValidationError: If elasticity is unrealistic
        """
        if not isinstance(elasticity, Decimal):
            elasticity = Decimal(str(elasticity))

        abs_elasticity = abs(elasticity)

        if abs_elasticity > ElasticityValidator.MAX_ELASTICITY:
            raise ValidationError(
                f"Elasticity {elasticity} exceeds realistic threshold "
                f"{ElasticityValidator.MAX_ELASTICITY}"
            )

        return True

    @staticmethod
    def validate_data_points(count: int) -> bool:
        """
        Validate if sufficient data points exist.

        Args:
            count: Number of data points

        Returns:
            True if valid

        Raises:
            ValidationError: If insufficient data points
        """
        if count < ElasticityValidator.MIN_DATA_POINTS:
            raise ValidationError(
                f"Insufficient data points: {count}. "
                f"Minimum required: {ElasticityValidator.MIN_DATA_POINTS}"
            )

        return True

    @staticmethod
    def validate_time_window(hours: float) -> bool:
        """
        Validate if time window is sufficient for analysis.

        Args:
            hours: Time window in hours

        Returns:
            True if valid

        Raises:
            ValidationError: If time window too small
        """
        if hours < ElasticityValidator.MIN_TIME_WINDOW_HOURS:
            raise ValidationError(
                f"Time window too small: {hours}h. "
                f"Minimum: {ElasticityValidator.MIN_TIME_WINDOW_HOURS}h"
            )

        return True
