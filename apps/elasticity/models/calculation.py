"""
ElasticityCalculation model for storing calculation results.

No user authentication - anonymous calculations with optional IP tracking.
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class ElasticityCalculation(models.Model):
    """
    Stores elasticity calculation results and metadata.

    Anonymous system - no user foreign keys.
    Optional IP tracking for analytics (not authentication).
    """

    METHOD_CHOICES = [
        ('MIDPOINT', 'Midpoint (Arc) Method'),
        ('REGRESSION', 'Log-Log Regression'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    CLASSIFICATION_CHOICES = [
        ('ELASTIC', 'Elastic Demand'),
        ('INELASTIC', 'Inelastic Demand'),
        ('UNITARY', 'Unitary Elastic'),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Anonymous tracking (optional)
    client_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP for rate limiting analytics (not auth)"
    )

    # Calculation parameters
    method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
        default='MIDPOINT'
    )

    start_date = models.DateTimeField(
        help_text="Start of analysis period"
    )

    end_date = models.DateTimeField(
        help_text="End of analysis period"
    )

    window_size = models.CharField(
        max_length=10,
        choices=[
            ('HOURLY', 'Hourly'),
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
        ],
        default='DAILY'
    )

    # Calculation results
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )

    elasticity_coefficient = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Calculated elasticity coefficient"
    )

    classification = models.CharField(
        max_length=20,
        choices=CLASSIFICATION_CHOICES,
        null=True,
        blank=True
    )

    # Statistical metrics
    confidence_interval_lower = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="95% confidence interval lower bound"
    )

    confidence_interval_upper = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="95% confidence interval upper bound"
    )

    r_squared = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        null=True,
        blank=True,
        help_text="R² for regression method"
    )

    standard_error = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True
    )

    # Data quality
    data_points_used = models.IntegerField(
        default=0,
        help_text="Number of observations used"
    )

    average_data_quality = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Average quality score of data points"
    )

    # Error handling
    error_message = models.TextField(
        null=True,
        blank=True
    )

    # Metadata
    calculation_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional calculation details"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'elasticity_calculations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['client_ip', '-created_at']),
        ]
        verbose_name = 'Elasticity Calculation'
        verbose_name_plural = 'Elasticity Calculations'

    def __str__(self):
        return f"Calculation {self.id} - {self.method} - {self.status}"

    @property
    def is_complete(self):
        """Check if calculation is complete."""
        return self.status == 'COMPLETED'

    @property
    def has_error(self):
        """Check if calculation failed."""
        return self.status == 'FAILED'

    @property
    def elasticity_magnitude(self):
        """Return absolute value of elasticity."""
        if self.elasticity_coefficient:
            return abs(self.elasticity_coefficient)
        return None

    def mark_completed(self):
        """Mark calculation as completed."""
        from django.utils import timezone
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def mark_failed(self, error_message: str):
        """Mark calculation as failed with error message."""
        from django.utils import timezone
        self.status = 'FAILED'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
