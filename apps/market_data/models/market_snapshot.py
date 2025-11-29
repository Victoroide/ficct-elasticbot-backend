"""
MarketSnapshot model for tracking USDT/BOB P2P market data.

Captures real-time market conditions from Binance P2P at regular intervals.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class MarketSnapshot(models.Model):
    """
    Captures USDT/BOB market data from Binance P2P at regular intervals.

    Each snapshot represents market conditions at a specific timestamp,
    including prices, volumes, and trader activity.

    Anonymous system - no user association required.
    """

    timestamp = models.DateTimeField(
        db_index=True,
        help_text="Time when snapshot was captured"
    )

    average_sell_price = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        validators=[
            MinValueValidator(Decimal('5.00')),
            MaxValueValidator(Decimal('15.00'))
        ],
        help_text="Average USDT sell price in BOB"
    )

    average_buy_price = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        validators=[
            MinValueValidator(Decimal('5.00')),
            MaxValueValidator(Decimal('15.00'))
        ],
        help_text="Average USDT buy price in BOB",
        null=True,
        blank=True
    )

    total_volume = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total USDT volume available. Null for OHLC sources that don't provide volume.",
        null=True,
        blank=True
    )

    spread_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        help_text="Price spread as percentage. Can be negative if sell_price < buy_price.",
        null=True,
        blank=True
    )

    num_active_traders = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of active traders in snapshot",
        default=0
    )

    data_quality_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Data quality score (0-1)",
        default=1.0
    )

    raw_response = models.JSONField(
        help_text="Raw API response for audit",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'market_snapshots'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'average_sell_price']),
            models.Index(fields=['-timestamp']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Market Snapshot'
        verbose_name_plural = 'Market Snapshots'

    def __str__(self):
        return f"Snapshot {self.timestamp} - {self.average_sell_price} BOB/USDT"

    @property
    def is_high_quality(self):
        """Check if snapshot meets quality standards."""
        return self.data_quality_score >= 0.7

    def calculate_quality_score(self):
        """
        Calculate data quality score based on multiple factors.

        Factors considered:
        - Volume adequacy (>100 USDT)
        - Number of traders (>5)
        - Price within expected range

        Returns:
            float: Quality score between 0.0 and 1.0
        """
        score = 1.0

        if self.total_volume < 100:
            score -= 0.3

        if self.num_active_traders < 5:
            score -= 0.2

        if self.spread_percentage and self.spread_percentage > 2:
            score -= 0.1

        self.data_quality_score = max(0.0, score)
        return self.data_quality_score
