"""
Serializer for elasticity calculation requests.
"""
from rest_framework import serializers
from datetime import timedelta
from django.utils import timezone
import pytz


class CalculationRequestSerializer(serializers.Serializer):
    """
    Validates calculation request parameters.

    Example request:
    {
        "method": "midpoint",
        "start_date": "2025-11-01T00:00:00Z",
        "end_date": "2025-11-18T23:59:59Z",
        "window_size": "daily"
    }

    Note: All dates are normalized to UTC for consistent database querying.
    """

    method = serializers.ChoiceField(
        choices=['midpoint', 'regression'],
        default='midpoint',
        help_text="Calculation method: midpoint (arc) or regression (log-log)"
    )

    start_date = serializers.DateTimeField(
        help_text="Start of analysis period (ISO 8601 format). Will be normalized to UTC."
    )

    end_date = serializers.DateTimeField(
        help_text="End of analysis period (ISO 8601 format). Will be normalized to UTC."
    )

    window_size = serializers.ChoiceField(
        choices=['hourly', 'daily', 'weekly'],
        default='daily',
        help_text="Data aggregation window"
    )

    def _normalize_to_utc(self, dt):
        """
        Normalize a datetime to UTC timezone.

        Handles:
        - Naive datetimes (assumes default timezone)
        - Aware datetimes in any timezone (converts to UTC)
        """
        if dt is None:
            return None

        # If naive, make it aware using the default timezone
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)

        # Convert to UTC
        return dt.astimezone(pytz.UTC)

    def validate_start_date(self, value):
        """Normalize start_date to UTC."""
        return self._normalize_to_utc(value)

    def validate_end_date(self, value):
        """Normalize end_date to UTC."""
        return self._normalize_to_utc(value)

    def validate(self, attrs):
        """Cross-field validation."""
        start_date = attrs['start_date']
        end_date = attrs['end_date']
        method = attrs['method']

        # End date must be after start date
        if end_date <= start_date:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date'
            })

        # Period cannot be in the future
        if start_date > timezone.now():
            raise serializers.ValidationError({
                'start_date': 'Start date cannot be in the future'
            })

        # Maximum period: 90 days
        max_period = timedelta(days=90)
        if (end_date - start_date) > max_period:
            raise serializers.ValidationError({
                'period': 'Analysis period cannot exceed 90 days'
            })

        # Minimum period depends on window size
        min_periods = {
            'hourly': timedelta(hours=24),  # At least 1 day
            'daily': timedelta(days=7),     # At least 1 week
            'weekly': timedelta(days=21),   # At least 3 weeks
        }

        min_period = min_periods[attrs['window_size']]
        if (end_date - start_date) < min_period:
            raise serializers.ValidationError({
                'period': f'For {attrs["window_size"]} window, need at least {min_period.days} days'
            })

        # Regression requires more data points
        if method == 'regression':
            min_regression_period = timedelta(days=14)
            if (end_date - start_date) < min_regression_period:
                raise serializers.ValidationError({
                    'method': 'Regression method requires at least 14 days of data'
                })

        return attrs
