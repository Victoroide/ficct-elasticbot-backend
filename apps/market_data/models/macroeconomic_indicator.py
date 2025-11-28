"""
MacroeconomicIndicator model for tracking Bolivian economic data.

Sources include INE (Instituto Nacional de Estadística) and BCB (Banco Central de Bolivia).
"""
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class MacroeconomicIndicator(models.Model):
    """
    Stores Bolivian macroeconomic indicators from official sources.

    Sources:
    - INE (Instituto Nacional de Estadística): Inflation data
    - BCB (Banco Central de Bolivia): Exchange rates

    Used to provide economic context for elasticity interpretations.
    """

    SOURCE_CHOICES = [
        ('INE', 'Instituto Nacional de Estadística'),
        ('BCB', 'Banco Central de Bolivia'),
        ('OTHER', 'Other Source'),
    ]

    date = models.DateField(
        unique=True,
        db_index=True,
        help_text="Date of indicator"
    )

    official_exchange_rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('6.00'))],
        help_text="Official BOB/USD exchange rate",
        null=True,
        blank=True
    )

    monthly_inflation_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        help_text="Monthly inflation rate as percentage",
        null=True,
        blank=True
    )

    accumulated_inflation = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text="Accumulated inflation for the year",
        null=True,
        blank=True
    )

    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default='BCB'
    )

    raw_data = models.JSONField(
        help_text="Raw data from source",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'macroeconomic_indicators'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date', 'source']),
            models.Index(fields=['-date']),
        ]
        verbose_name = 'Macroeconomic Indicator'
        verbose_name_plural = 'Macroeconomic Indicators'

    def __str__(self):
        return f"{self.source} - {self.date}"
