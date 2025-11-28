"""
Comprehensive tests for utils validators.

Tests validation functions for API inputs.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError

from utils.validators import (
    DateRangeValidator,
    PriceValidator,
    VolumeValidator,
    ElasticityValidator,
    OutlierDetector
)


class TestDateRangeValidator:
    """Tests for DateRangeValidator class."""

    def test_valid_date_range(self):
        """Test valid date range passes validation."""
        start = datetime.now() - timedelta(days=7)
        end = datetime.now() - timedelta(hours=1)

        result = DateRangeValidator.validate_date_range(start, end)

        assert result is True

    def test_invalid_date_range_end_before_start(self):
        """Test end date before start date fails validation."""
        start = datetime.now()
        end = datetime.now() - timedelta(days=7)

        with pytest.raises(ValidationError):
            DateRangeValidator.validate_date_range(start, end)

    def test_date_range_too_long(self):
        """Test date range exceeding max days fails validation."""
        start = datetime.now() - timedelta(days=400)
        end = datetime.now() - timedelta(hours=1)

        with pytest.raises(ValidationError):
            DateRangeValidator.validate_date_range(start, end)

    def test_date_range_same_time_fails(self):
        """Test same time range fails validation."""
        now = datetime.now()

        with pytest.raises(ValidationError):
            DateRangeValidator.validate_date_range(now, now)

    def test_date_range_future_end(self):
        """Test future end date fails validation."""
        start = datetime.now()
        end = datetime.now() + timedelta(days=7)

        with pytest.raises(ValidationError):
            DateRangeValidator.validate_date_range(start, end)


class TestPriceValidator:
    """Tests for PriceValidator class."""

    def test_valid_price(self):
        """Test valid price passes validation."""
        result = PriceValidator.validate_price(Decimal('7.05'))

        assert result is True

    def test_valid_price_boundary_low(self):
        """Test valid price at lower boundary."""
        result = PriceValidator.validate_price(Decimal('5.00'))

        assert result is True

    def test_valid_price_boundary_high(self):
        """Test valid price at upper boundary."""
        result = PriceValidator.validate_price(Decimal('15.00'))

        assert result is True

    def test_invalid_price_too_low(self):
        """Test price below range fails validation."""
        with pytest.raises(ValidationError):
            PriceValidator.validate_price(Decimal('4.00'))

    def test_invalid_price_too_high(self):
        """Test excessively high price fails validation."""
        with pytest.raises(ValidationError):
            PriceValidator.validate_price(Decimal('100.00'))

    def test_price_decimal_precision(self):
        """Test decimal precision is preserved."""
        result = PriceValidator.validate_price(Decimal('7.05'))

        assert result is True


class TestVolumeValidator:
    """Tests for VolumeValidator class."""

    def test_valid_volume(self):
        """Test valid volume passes validation."""
        result = VolumeValidator.validate_volume(Decimal('50000.00'))

        assert result is True

    def test_valid_volume_at_minimum(self):
        """Test volume at minimum threshold passes."""
        result = VolumeValidator.validate_volume(Decimal('100.00'))

        assert result is True

    def test_invalid_volume_too_low(self):
        """Test volume below minimum fails validation."""
        with pytest.raises(ValidationError):
            VolumeValidator.validate_volume(Decimal('50.00'))

    def test_volume_large_value(self):
        """Test large volume value is valid."""
        result = VolumeValidator.validate_volume(Decimal('999999999.99'))

        assert result is True


class TestElasticityValidator:
    """Tests for ElasticityValidator class."""

    def test_valid_elasticity_inelastic(self):
        """Test valid inelastic elasticity."""
        result = ElasticityValidator.validate_elasticity_result(Decimal('-0.75'))

        assert result is True

    def test_valid_elasticity_elastic(self):
        """Test valid elastic elasticity."""
        result = ElasticityValidator.validate_elasticity_result(Decimal('-1.85'))

        assert result is True

    def test_valid_elasticity_unitary(self):
        """Test valid unitary elasticity."""
        result = ElasticityValidator.validate_elasticity_result(Decimal('-1.0'))

        assert result is True

    def test_valid_elasticity_positive(self):
        """Test positive elasticity for Giffen goods."""
        result = ElasticityValidator.validate_elasticity_result(Decimal('0.5'))

        assert result is True

    def test_invalid_elasticity_too_high(self):
        """Test excessively high elasticity fails validation."""
        with pytest.raises(ValidationError):
            ElasticityValidator.validate_elasticity_result(Decimal('-15.0'))

    def test_validate_data_points_valid(self):
        """Test valid data points count."""
        result = ElasticityValidator.validate_data_points(20)

        assert result is True

    def test_validate_data_points_insufficient(self):
        """Test insufficient data points fails validation."""
        with pytest.raises(ValidationError):
            ElasticityValidator.validate_data_points(5)

    def test_validate_time_window_valid(self):
        """Test valid time window."""
        result = ElasticityValidator.validate_time_window(24.0)

        assert result is True

    def test_validate_time_window_too_short(self):
        """Test too short time window fails validation."""
        with pytest.raises(ValidationError):
            ElasticityValidator.validate_time_window(2.0)


class TestOutlierDetector:
    """Tests for OutlierDetector class."""

    def test_detect_outlier_normal_value(self):
        """Test normal value is not detected as outlier."""
        result = OutlierDetector.detect_outlier(7.05, 7.00, 0.10)

        assert result is False

    def test_detect_outlier_outlier_value(self):
        """Test outlier value is detected."""
        result = OutlierDetector.detect_outlier(15.0, 7.00, 0.50)

        assert result is True

    def test_detect_outlier_zero_std(self):
        """Test zero standard deviation returns False."""
        result = OutlierDetector.detect_outlier(7.05, 7.00, 0.0)

        assert result is False

    def test_detect_outlier_boundary(self):
        """Test value above z-score threshold boundary."""
        # Z-score threshold is 3.0, so value = mean + 3.1*std should be detected
        result = OutlierDetector.detect_outlier(10.1, 7.00, 1.0)

        assert result is True
